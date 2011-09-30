#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Martín Chikilian <slacklinucs@gmail.com>
# License: GPL v3.0

"""
A GUI interface to cuevanaapi
"""

import os
import sys
from ordereddict import OrderedDict
import urllib

import Queue

from multiprocessing import Process

from PyQt4 import QtGui, QtCore

from . import __version__, PKG_PATH
import cuevanaapi
from downloaders import (megaupload_gui, NotValidMegauploadLink,
                        NotAvailableMegauploadContent,
                        smart_urlretrieve)
from utils import get_config, write_config, background_process, createDownloadDir

import pdb

def item_to_sort(item):
    if isinstance(item, cuevanaapi.Episode):
        return u'S%.2dE%2.d' % (item.season, item.episode)
    else:
        return unicode(item.pretty_title)

def _modify_download_item(obj, args):
    status, size, progress, speed, eta = (args[0], args[1], args[2],
        args[3], args[4])
    tree_element = list(obj)

    if status:
        tree_element[1] = status

    if size:
        tree_element[2] = '%s MB' % int(size / (1024**2))

    if progress:
        tree_element[3] = '%3d%%' % (progress * 100 / size if progress != "Finished" else 100)

    if speed:
        tree_element[4] = speed

    if eta:
        tree_element[5] = eta

    if isinstance(tree_element, list) and tree_element:
        return tree_element
    else:
        return None

def _create_frame(obj, name, layout='hbox'):
    """ Create frame `name` and link an optional `layout` with it """
    setattr(obj, "%s_frame" % name, QtGui.QFrame(obj))
    setattr(obj, "%s_layout" % name, QtGui.QHBoxLayout(getattr(obj, "%s_frame" % name))
            if layout == 'hbox' else QtGui.QVBoxLayout(getattr(obj, "%s_frame" % name)))
    getattr(obj, "%s_frame" % name).setLayout(getattr(obj, "%s_layout" % name))

def create_menu_item(menu_parent, menu_title, menu_shortcut = None, bitmap = None,
    menu_status_tip = None):
    if bitmap != None:
        item = QtGui.QAction(QtGui.QIcon(os.path.join(PKG_PATH, 'resources', bitmap)),
            menu_title, menu_parent)
    else:
        item = QtGui.QAction(menu_title, menu_parent)

    if menu_shortcut != None:
        item.setShortcut(menu_shortcut)

    if menu_status_tip != None:
        item.setStatusTip(menu_status_tip)

    menu_parent.addAction(item)

    return item

def create_process(target_function, cmd_list):
    _process = Process(target=target_function,
                        args=(cmd_list,))
    return _process if _process else None


class _CuevanaThreads(QtCore.QThread):
    """ Base class for threads used in this GUI program """

    def cancel(self):
        self._cancel = True

    def signal_results(self, signal, args):
        self.emit(QtCore.SIGNAL(signal), args)
        if not args[0] and args[0] != 0:
            self.cancel()


class _ProcessTerms(_CuevanaThreads):
    """ Thread class to process input terms """

    def render(self, title, title_type):
        """ Render passed parameters """

        self._cancel = False
        self.title = str(title)
        self.title_type = title_type
        self.contents = Queue.Queue()
        self.found = False
        self.start()

    def run(self):
        filter = None
        api = cuevanaapi.CuevanaAPI(filter)

        while not self._cancel:
            if self.title.startswith(cuevanaapi.URL_BASE) and self.title_type == "show":
                try:
                    content = cuevanaapi.dispatch(self.title)

                    if content:
                        self.contents.put(content)
                    else:
                        self.signal_results((False, "Not valid URL of a cuevana's movie/episode"))
                # except NotValidURL:
                #    self.signal_results((False, "Not valid URL of a cuevana's movie/episode"))
                except Exception, e:        #Fix me
                    self.signal_results((False, 'Error: %s' % e))
                finally:
                    self.cancel()
            elif self.title_type == "show":
                # show
                # print "Searching '%s'...\n" % self.title
                try:
                    show = api.get_show(self.title)

                    if show:
                       self.found = True
                       episodes = [ep for season in show.seasons for ep in season]
                       for episode in episodes:
                           self.contents.put(episode)
                    else:
                       self.signal_results((False, "No show was found for '%s'." % self.title))
                except Exception, e:            #Fix me
                    self.signal_results((False, 'Error: %s' % e))
                finally:
                    self.cancel()
            else:
                #movie
                # print "Searching '%s'...\n" % str(self.title.text())
                try:
                    results = api.search(self.title)

                    if results:
                        for result in results:
                            if isinstance(result, cuevanaapi.Show):
                                continue
                            else:
                                self.found = True
                                self.contents.put(result)
                    #TODO order result by relevance as done with Shows ?
                    #or (better) check len of results and turns interactive if are many
                    else:
                        self.signal_results((False, "No movie was found for '%s'." % self.title))
                except Exception, e:        #FIX ME this is crap
                    self.signal_results((False, 'Error: %s' % e))
                finally:
                    self.cancel()

    def signal_results(self, args):
        super(_ProcessTerms, self).signal_results('result_ready(PyQt_PyObject)', args)


class _DownloadContents(_CuevanaThreads):
    """ Thread class used to download contents: video and (optionally), subtitles """

    def render(self, main, content, language, max_rate=None):
        """ Render passed parameters """

        self._cancel = False
        self._main = main
        self._content = content
        self._language = language
        self._max_rate = max_rate
        self._cb_triggered = self._process = False
        self._triggered = True
        self.start()

    def run(self):
        while not self._cancel:
            config = get_config()
            format = config.get('main', 'file_format')

            download_dir = config.get('main', 'download_dir')

            if isinstance(self._content, cuevanaapi.Episode):
                download_dir = os.path.join(download_dir, self._content.show, 'Season_%.2d' % self._content.season)
            else:
                download_dir = os.path.join(download_dir, self._content.title)

            try:
                createDownloadDir(download_dir)
            except Exception, e:        #Fix me
                self.update_download_status(('Error: %s' % e, None, None, None, None))

            mu_url = [link for link in self._content.sources if 'megaupload' in link][0]
            self._filename = os.path.join(download_dir, self._content.filename(format=format, extension='mp4'))

            self._command_list = config.get('main', 'player').split()

            if '{file}' in self._command_list:
                self._command_list[self._command_list.index('{file}')] = self._filename
            else:
                self._command_list.append(self._filename)

            # Try to download subtitles right before the title/episode as if 'Also play' is selected
            # it will need them
            try:
                smart_urlretrieve(self._content.subs[self._language],
                                os.path.join(download_dir, self._content.filename(format=format)),
                                self._content.url)
            except Exception, e:        #Fix me
                # self.update_download_status(('Error: %s' % e, None, None, None, None))
                pass # no subs for this title/episode

            try:
                megaupload_gui(self, mu_url, self._filename, kbps=128, max_rate=self._max_rate)
                if self._process: self._process.join()
            except AssertionError:  # multiprocess error when process hasn't start()ed
                pass
            except NotAvailableMegauploadContent:
                self.update_download_status(('Megaupload does not have this file available', None,
                                            None, None, None))
            except NotValidMegauploadLink:
                self.update_download_status(('Not valid megaupload link given', None, None, None, None))

            self.cancel()

    def update_download_status(self, args):
        super(_DownloadContents, self).signal_results('update_download_status(PyQt_PyObject)',
                                                        (self._content, args))


class TreeItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        try:
            return self.itemData[column]
        except IndexError:
            return None

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            data = [None for v in range(columns)]
            item = TreeItem(data, self)
            self.childItems.insert(position, item)

        return True

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)

        return 0

class TitlesTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, data, parent=None):
        super(TitlesTreeModel, self).__init__(parent)
        self._parent = parent
        self.rootItem = TreeItem(("Titles",))
        self.show = False
        self.childs_status = {}
        self.setupModelData(data, self.rootItem)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole:
            try:
                if self.show:
                    if isinstance(item.data(index.column()), cuevanaapi.Episode):
                        return '%.2d - %s' % (item.data(index.column()).episode,
                            item.data(index.column()).title.strip())
                    else:
                        return item.data(index.column())
                else:
                    return item.data(index.column())[0].title.strip()
            except Exception, e:
                print e
                return "N/A"
        elif role == QtCore.Qt.CheckStateRole:
            if isinstance(item.data(index.column()), cuevanaapi.Episode) \
                or not isinstance(item.data(index.column()), list):
                value = self.childs_status.get(item.data(index.column()), 0)
            else:
                value = self.childs_status.get(item.data(index.column())[0], 0)
            return QtCore.Qt.Unchecked if not value else QtCore.Qt.Checked
        else:
            return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setupModelData(self, data, parent):
        parents = [parent]
        seasons = []

        if isinstance(data.values()[0], OrderedDict):
            new_itemData = list(parents[0].itemData)
            new_itemData[0] = data.keys()[0]
            parents[0].itemData = new_itemData
            self.show = True

        for item in data.iteritems():
            if len(data) == 1:
                if isinstance(data.values()[0], OrderedDict):
                    for show_data in data.values()[0].iteritems():
                        if not show_data[0] in seasons:
                            seasons.append(show_data[0])
                            self.new_season = TreeItem((show_data[0],), parents[0])
                            parents[0].appendChild(self.new_season)
                            parents.append(self.new_season)
                            for episode in show_data[1]:
                                parents[-1].appendChild(TreeItem((episode,),
                                    parents[-1]))
                else:
                    parents[0].appendChild(TreeItem((item[1],), parents[0]))
            else:
                parents[0].appendChild(TreeItem((item[1],), parents[0]))

    def setData(self, index, value, role):
        if index.isValid():
            item = index.internalPointer()
            if role == QtCore.Qt.CheckStateRole:
                if isinstance(item.data(index.column()), cuevanaapi.Episode):
                    self.childs_status[item.data(index.column())] = value.toInt()[0]
                elif not isinstance(item.data(index.column()), list):
                    self.childs_status[item.data(index.column())] = value.toInt()[0]
                    for i in self.rootItem.childItems:
                        if i.itemData[0] == item.data(index.column()):
                            for j in i.childItems:
                                self.childs_status[j.itemData[0]] = value.toInt()[0]
                else:
                    self.childs_status[item.data(index.column())[0]] = value.toInt()[0]
            self._parent.download_button.setFocus()
            return True
        return False

class DownloadTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super(DownloadTreeModel, self).__init__(parent)
        self._parent = parent
        self.rootItem = TreeItem(' ' * 6)
        self.columns = { 0: 'Name',
                         1: 'Status',
                         2: 'Size',
                         3: 'Progress',
                         4: 'Speed',
                         5: 'Remaining Time' }

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def columnName(self, column):
        return self.columns[column]

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole:
            return item.data(index.column())
        else:
            return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.rootItem

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.columnName(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        # parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position + rows - 1)
        #success = parentItem.insertChildren(position, rows,
        #        self.rootItem.columnCount())
        self.endInsertRows()

        #return success
        return True

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def removeRow(self, index, parent=QtCore.QModelIndex()):
        # parentItem = self.getItem(parent)
        item = index.internalPointer()
        self.beginRemoveRows(parent, index.row(), index.row())

        for child_item in self.rootItem.childItems:
            if child_item.itemData[0] == item.data(index.column()):
                self.rootItem.childItems.remove(child_item)
        self.endRemoveRows()

        #return success
        return True

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setupModelData(self, data, parent):
        parents = [parent]

        for item in data:
            not_add = False
            add_item = item.title.strip()

            if isinstance(item, cuevanaapi.Episode):
                add_item = '%s - Season %.2d - Episode %.2d - %s' % (item.show, item.season, item.episode,
                                                                    add_item)

            for child_item in parents[-1].childItems:
                if add_item == child_item.itemData[0]:
                    not_add = True
            if not not_add:
                print "Adding '%s' to downloads queue" % add_item
                parents[-1].appendChild(TreeItem((add_item, 'Queued', None, None, None, None, item.cid), parents[-1]))
                # self._parent.download(item)
                self._parent.enqueue(item)


class _ContentFrame(QtGui.QFrame):
    """ Frame used to show title's contents """

    def __init__(self, parent):
        super(_ContentFrame, self).__init__(parent)
        layout = QtGui.QGridLayout()
        self.title_thumbnail = QtGui.QLabel()
        self.title = QtGui.QLabel('<center>No info available</center>')
        self.title_plot = QtGui.QLabel()
        self.title_sources = QtGui.QLabel()
        # self.title_subs = QtGui.QLabel()
        # for item in self.title_sources, self.title_subs:
        self.title_sources.setOpenExternalLinks(True)

        for item in self.title, self.title_plot, self.title_sources:
            item.setWordWrap(True)

        layout.addWidget(self.title_thumbnail, 0, 0)
        layout.addWidget(self.title, 1, 0)
        layout.addWidget(self.title_plot, 2, 0, 1, 2)
        layout.addWidget(self.title_sources, 3, 0)
        # layout.addWidget(self.title_subs, 4, 0)
        layout.setSizeConstraint(QtGui.QLayout.SetMinAndMaxSize)
        self.setLayout(layout)


class _SettingsWindow(QtGui.QDialog):
    """ Settings dialog (modal) """

    def __init__(self, parent):
        super(_SettingsWindow, self).__init__(parent, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)
        self._parent = parent
        self.setFixedSize(400, 240)
        layout = QtGui.QGridLayout()
        _create_frame(self, 'player')
        self._lbl_player = QtGui.QLabel('Player:', self.player_frame)
        config = get_config()
        player = config.get('main', 'player')
        self.player = QtGui.QLineEdit(player if player else '', self.player_frame)

        for widget in self._lbl_player, self.player:
            self.player_layout.addWidget(widget)
        _create_frame(self, 'down_folder')
        self._lbl_download_folder = QtGui.QLabel('Download folder:', self.down_folder_frame)
        folder = config.get('main', 'download_dir')
        self.download_folder = QtGui.QLineEdit(folder if folder else '', self.down_folder_frame)
        self.folder_open = QtGui.QPushButton()
        self.folder_open.setIcon(QtGui.QIcon(os.path.join(PKG_PATH, 'resources', 'folder_open.png')))

        for widget in self._lbl_download_folder, self.download_folder:
            self.down_folder_layout.addWidget(widget)
        _create_frame(self, 'languages')
        self._lbl_languages = QtGui.QLabel('Subtitles language\n(if available):', self.languages_frame)
        self.cb_languages = QtGui.QComboBox(self.languages_frame)
        self.cb_languages.setEditable(False)

        for widget in self._lbl_languages, self.cb_languages:
            self.languages_layout.addWidget(widget)
        _create_frame(self, 'max_rate')
        self._lbl_max_rate = QtGui.QLabel('Max download rate\n(this is not stored in config file):', self.max_rate_frame)
        self.max_rate = QtGui.QLineEdit(str(self._parent.max_rate) if self._parent.max_rate
                                        else '', self.max_rate_frame)

        for widget in self._lbl_max_rate, self.max_rate:
            self.max_rate_layout.addWidget(widget)
        self.ok_button = QtGui.QPushButton('Ok')
        self.ok_button.setDefault(True)
        self.cancel_button = QtGui.QPushButton('Cancel')
        layout.addWidget(self.player_frame, 0, 0)
        layout.addWidget(self.down_folder_frame, 1, 0)
        layout.addWidget(self.folder_open, 1, 1)
        layout.addWidget(self.languages_frame, 2, 0)
        layout.addWidget(self.max_rate_frame, 3, 0)
        layout.addWidget(self.ok_button, 4, 0)
        layout.addWidget(self.cancel_button, 4, 1)
        self.setLayout(layout)
        self.download_folder.setToolTip('Enter here absolute path of your preferred download folder')
        self.cb_languages.setToolTip('Subtitles language')
        self.max_rate.setToolTip('Maximum download rate in Kbps. Leave empty for unlimited')

        for lang in ('ES', 'EN', 'PT'):
            self.cb_languages.addItem(lang)
        self.default_lang = self.cb_languages.findText(self._parent._get_configured_language(), QtCore.Qt.MatchExactly)
        self.cb_languages.setCurrentIndex(self.default_lang if self.default_lang != -1 else 0)
        self.folder_open.clicked.connect(self._select_download_folder)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def accept(self):
        self.set_configuration(str(self.player.text()), str(self.download_folder.text()), str(self.cb_languages.currentText()))
        super(_SettingsWindow, self).accept()

    def _select_download_folder(self):
        directory = QtGui.QFileDialog.getExistingDirectory(self, "Browse for folder",
                              os.path.join(os.path.expanduser("~"), ""),
                              QtGui.QFileDialog.ShowDirsOnly | QtGui.QFileDialog.DontResolveSymlinks)
        if directory:
            self.download_folder.setText(directory)

    def set_configuration(self, player, directory='', language='ES'):
        config = get_config()
        if not player:
            player = 'vlc {file}'

        if directory and os.path.exists(directory):
            config.set('main', 'download_dir', directory)
        config.set('main', 'player', player)
        config.set('main', 'language', language)
        write_config(config)


class _AboutWindow(QtGui.QDialog):
    """ About dialog (modal) """

    def __init__(self, parent):
        super(_AboutWindow, self).__init__(parent, QtCore.Qt.WindowTitleHint | \
                QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint)
        self._parent = parent
        self.setFixedSize(275, 350)
        layout = QtGui.QGridLayout()
        self._lbl_title = QtGui.QLabel('<b>CuevanaLinks-GUI (%s) - Beta</b>' % __version__)
        self._lbl_descr = QtGui.QLabel('Qt UI for CuevanaLinks')
        self._lbl_author = QtGui.QLabel(u'''<i>Author: Martín Chikilian <slacklinucs at gmail dot com>
        using the API provided by Martín Gaitán</i>. None of the authors are somehow affiliated with Cuevana.tv
        nor are responsibles of the contents provided by the site. Any complaints about behavior of the program
        have to be directed to them but if you have complaints about Cuevana, we won't be able to help you much.''')
        self._lbl_author.setWordWrap(True)
        self.ok_button = QtGui.QPushButton('Ok')
        self.ok_button.setDefault(True)
        layout.addWidget(self._lbl_title, 0, 0)
        layout.addWidget(self._lbl_descr, 1, 0)
        layout.addWidget(self._lbl_author, 2, 0)
        layout.addWidget(self.ok_button, 3, 0)
        self.setLayout(layout)
        self.ok_button.clicked.connect(self.accept)


class _CuevanaGUI(QtGui.QFrame):
    """ Main GUI class """

    def __init__(self, parent):
        super(_CuevanaGUI, self).__init__(parent)
        self._parent = parent
        self.max_rate = None
        self.language = self._get_configured_language()
        self._process_terms = _ProcessTerms()
        self._download_contents = _DownloadContents()
        self.downloads_queue = Queue.Queue()
        self._downloading = False
        layout = QtGui.QGridLayout(self)
        _create_frame(self, 'title')
        self._lbl_title = QtGui.QLabel('Search:', self.title_frame)
        self.title = QtGui.QLineEdit(self.title_frame)
        self.current_title_type = "movie"
        self.cb_title_type = QtGui.QComboBox(self.title_frame)
        self.cb_title_type.setEditable(False)
        for title_type in 'Movie', 'Show':
            self.cb_title_type.addItem(title_type)

        for widget in self._lbl_title, self.title, self.cb_title_type:
            self.title_layout.addWidget(widget)
        _create_frame(self, 'title_episode', 'vbox')
        _create_frame(self, 'download_play')
        self.download_button = QtGui.QPushButton('Download selected')
        self.download_button.setEnabled(False)
        self.download_button.setMaximumWidth(375)

        try:
            self.title.setPlaceholderText('Type in Movie/Show or URL')
        except AttributeError:
            pass

        self.title.setToolTip("Look for a movie or show with this title or URL")
        self.tabs = QtGui.QTabWidget(self)
        self.tabs.setFocus()
        _create_frame(self, 'main')
        self.main_tree = QtGui.QTreeView(self.main_frame)
        # self.main_tree.setMinimumSize(300, 450)
        self.content_frame = _ContentFrame(self.main_frame)
        self.content_frame.setMinimumSize(400, 500)
        self.scrollbar_area = QtGui.QScrollArea()
        self.scrollbar_area.setWidget(self.content_frame)

        for widget in self.main_tree, self.scrollbar_area:
             self.main_layout.addWidget(widget)
        # self.main_layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        self.downloads_tree = QtGui.QTreeView()
        self.downloads_model = DownloadTreeModel(self)
        self.downloads_tree.setModel(self.downloads_model)
        self.downloads_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tabs.addTab(self.main_frame, "Results")
        self.tabs.addTab(self.downloads_tree, "Downloads")
        self.lbl_status = QtGui.QLabel(self)
        layout.addWidget(self.title_frame, 0, 0)
        layout.addWidget(self.tabs, 1, 0)
        layout.addWidget(self.download_button, 2, 0)
        layout.addWidget(self.lbl_status, 3, 0)
        self.setLayout(layout)

        self.title.returnPressed.connect(self._search_terms)
        self.main_tree.clicked.connect(self._titles_clicked)
        self.connect(self._process_terms, QtCore.SIGNAL('result_ready(PyQt_PyObject)'), self._make_list)
        self._process_terms.finished.connect(self._process_finished)
        self.connect(self._download_contents, QtCore.SIGNAL('update_download_status(PyQt_PyObject)'), self._update_download_status)
        self._download_contents.finished.connect(self._download_finished)
        self.cb_title_type.currentIndexChanged.connect(self._set_title_type)
        self.download_button.clicked.connect(self._prepare_downloads)
        self.downloads_tree.customContextMenuRequested.connect(self.open_menu)

    def _set_title_type(self, index):
        self.current_title_type = "show" if index == 1 else "movie"
        self.title.setFocus()

    def _search_terms(self):
        if self.title:
            self.lbl_status.clear()
            self.update_status_label('Searching, please wait...')
            self.enable_search(False)
            self._kill_thread(self._process_terms)
            self.titles_content = OrderedDict()
            self._process_terms.render(self.title.text(), self.current_title_type)

    def _make_list(self, result):
        if not result[0]:
            self.update_status_label(result[1], True)

    def _process_finished(self):
        processing = True
        if self._process_terms.found:
            self.update_status_label('Creating list, this can take a while...')
        try:
            while processing:
                content = self._process_terms.contents.get_nowait()
                self.update_window()
                self._add_contents(content)
        except Queue.Empty:
            processing = False
            if self.titles_content:
                self.titles_model = TitlesTreeModel(self.titles_content, self)
                self.main_tree.setModel(self.titles_model)
                self.download_button.setEnabled(True)
                self.lbl_status.clear()

        self.enable_search()
        self.title.setFocus()
        self.update_window()

    def _titles_clicked(self, index):
        self.lbl_status.clear()
        self.update_status_label('Loading...')
        item = index.internalPointer()
        display_item = False

        if self.titles_model.show:
          if isinstance(item.data(index.column()), cuevanaapi.Episode):
              display_item = item.data(index.column())
        else:
            display_item = item.data(index.column())[0]

        if display_item:
            self.display(display_item)
        self.lbl_status.clear()

    def _add_contents(self, content):
        try:
            if isinstance(content, cuevanaapi.Episode):
                if not self.titles_content.has_key(content.show.strip()):
                    self.titles_content[content.show.strip()] = OrderedDict()
                if self.titles_content[content.show.strip()].has_key('Season %.2d' % content.season):
                    self.titles_content[content.show.strip()]['Season %.2d' % content.season].append(content)
                else:
                    self.titles_content[content.show.strip()]['Season %.2d' % content.season] = [content]
            else:
                self.titles_content[content.title.strip()] = [content]
        except Exception:
            self.update_status_label('Error: your list could be incomplete due to issues in the site', True)
            return False

    def display(self, content):
        """auxiliar function to practice DRY principle"""

        if content.thumbnail:
            title_thumbnail = QtGui.QPixmap()
            title_thumbnail.loadFromData(urllib.urlopen(content.thumbnail).read())

            if title_thumbnail:
                self.content_frame.title_thumbnail.setPixmap(title_thumbnail)

        try:
            self.content_frame.title.setText('<b>%s</b>' % content.title)
        except Exception:
            self.content_frame.title.setText('N/A')

        try:
            self.content_frame.title_plot.setText('<i>%s</i>' % content.plot)
        except Exception:
            self.content_frame.title_plot.setText('N/A')

        try:
            self.content_frame.title_sources.setText('\n'.join(["<a href='%s'>%s</a>" % \
                (source, source) for source in content.sources]))
            # self.content_frame.title_subs.setText("\n<a href='" + content.subs[self.language] +
            #                                   "'>" + content.subs[self.language] + "</a>")
        except:
            self.content_frame.title_sources.setText('Error: Unable to get links')

        self.update_window()

    def _prepare_downloads(self):
        self.downloads_content = []
        for item in self.titles_model.childs_status.iteritems():
            if item[1] == 2 and self.downloads_content.count(item[0]) == 0 and \
                isinstance(item[0], cuevanaapi.Content):
                self.downloads_content.append(item[0])

        # Sorts list of movies/episodes by index
        self.downloads_content.sort(key=item_to_sort)   # TODO: a better sorting system?

        if self.downloads_content:
            self.downloads_model.setupModelData(self.downloads_content, self.downloads_model.rootItem)
            self.downloads_model.insertRows(self.downloads_model.rowCount(), len(self.downloads_content))

    def enqueue(self, item):
        self.downloads_queue.put_nowait(item)
        self.download()

    def download(self):
        if not self._downloading:
            try:
                item = self.downloads_queue.get_nowait()
            except Queue.Empty:
                self.update_status_label("All downloads finished or no items to download", True)
                self.update_window()
            else:
                self._downloading = True
                self._kill_thread(self._download_contents)
                self._download_contents.render(self, item, self.language,
                    self.max_rate if self.max_rate else None)

    def _download_finished(self):
        self._downloading = False
        self.download()

    def _update_download_status(self, args):
        content = args[0]
        values = args[1]
        child_item = None

        for child_item in self.downloads_model.rootItem.childItems:
            if content.cid == child_item.itemData[6]:
                break

        if child_item:
            new_child_item = _modify_download_item(child_item.itemData, values)

            if new_child_item:
                child_item.itemData = new_child_item
        self.downloads_model.reset()

    def open_menu(self, position):
        indexes = self.downloads_tree.selectedIndexes()

        if not len(indexes) > 0:
            return False
        index = indexes[0]
        menu = QtGui.QMenu()
        self._play_action = create_menu_item(menu, '&Play', '', '', 'Play video')
        self._play_action.setEnabled(True if self._download_contents._cb_triggered else False)
        self._stop_action = create_menu_item(menu, '&Stop', '', '', 'Stop video')
        self._stop_action.setEnabled(True if self._download_contents._triggered else False)
        self._remove_action = create_menu_item(menu, '&Remove', '', '', 'Remove video')
        action = menu.exec_(self.downloads_tree.viewport().mapToGlobal(position))

        if action == self._play_action:
            if self._download_contents._process and self._download_contents._process.is_alive():
                self.update_status_label("CuevanaLinks is already playing the file!", True)
            else:
                self._download_contents._process = create_process(background_process,
                    self._download_contents._command_list)

                if self._download_contents._process:
                    try:
                        self._download_contents._process.start()
                    except Exception, e:
                        self.update_status_label("Could not start player! Exception: %s" % e,
                                                True)
                        self._download_contents._process = None
        elif action == self._stop_action:
            self._download_contents.update_download_status(('Stopped', '', '', '', ''))
            self._kill_thread(self._download_contents)
        elif action == self._remove_action:
            self._kill_thread(self._download_contents)
            self.downloads_model.removeRow(index)

    def enable_search(self, enabled=True):
        self.title.setEnabled(enabled)

    def update_window(self):
        self._parent.repaint()
        self._parent.update()
        self._parent.app.processEvents()

    def _kill_thread(self, name):
        if name.isRunning():
            name.cancel()

    def _settings_dialog(self):
        self.settings_dialog = _SettingsWindow(self)
        set_dlg_ret = self.settings_dialog.exec_()

        if set_dlg_ret:
            if self.settings_dialog.max_rate.text():
                try:
                    self.max_rate = float(self.settings_dialog.max_rate.text())
                except ValueError:
                    pass
            else:
                self.max_rate = None

            self.language = str(self.settings_dialog.cb_languages.currentText())
            print "Max rate set to: '%s' and language to: '%s'" % ('Unlimited' if not self.max_rate else self.max_rate, self.language)

    def _about_dialog(self):
        self.about_dialog = _AboutWindow(self)
        self.about_dialog.exec_()

    def _get_configured_language(self):
        config = get_config()
        try:
            language = config.get('main', 'language')
        except:
            language = 'ES'
        return language if language else 'ES'

    def update_status_label(self, content, color=False):
        self.lbl_status.setText(content if not color else "<font color='red'>" + content + "</font>")
        self.update_window()

_CuevanaGUI.__doc__ = ("CuevanaLinks %s - 2011 Martin Gaitán\n"
               "A program to retrieve movies and series "
               "(or links to them) from cuevana.tv"
                % __version__ )


class MainWindow(QtGui.QMainWindow):
    " Main window class "

    def __init__(self):
        self.app = QtGui.QApplication(sys.argv)
        super(MainWindow, self).__init__()
        cuevana_gui = _CuevanaGUI(self)
        self.setWindowTitle('CuevanaLinks-GUI (%s) - Beta' % __version__)
        self.resize(800, 600)
        menu_bar = QtGui.QMenuBar()
        self.m_file = menu_bar.addMenu('&File')
        self.a_settings = create_menu_item(self.m_file, '&Settings', 'Ctrl+P', 'configure.png',
             'Application settings')
        self.m_file.addSeparator()
        self.a_quit = create_menu_item(self.m_file, '&Quit', 'Ctrl+Q', 'exit.png', 'Exit application')
        self.m_help = menu_bar.addMenu('&Help')
        self.a_about = create_menu_item(self.m_help, '&About', '', 'info.png', 'About application')
        self.setMenuBar(menu_bar)
        self.setCentralWidget(cuevana_gui)
        self.center()
        self.a_settings.triggered.connect(cuevana_gui._settings_dialog)
        self.a_about.triggered.connect(cuevana_gui._about_dialog)
        self.a_quit.triggered.connect(self.on_quit)

    def center(self):
        _screen = QtGui.QDesktopWidget().screenGeometry()
        _size = self.geometry()
        self.move((_screen.width()-_size.width())/2, (_screen.height()-_size.height())/2)

    def on_quit(self):
        print "Quitting app..."
        self.app.quit()

    def main(self):
        self.show()
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    mw = MainWindow()
    mw.main()
