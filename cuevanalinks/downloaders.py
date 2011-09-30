#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Martín Gaitán <gaitan AT gmail DOT com>
# Licence: GPL v3.0

import os
import sys
import time
import urllib2
import shutil
import cookielib

from pyquery import PyQuery as pq


from progressbar import __version__ as pb_version, \
                        ProgressBar, Percentage, Bar, ETA

try:
    from progressbar import ProgressBarWidget
except ImportError:
    #API changed in 2.3
    from progressbar import Widget as ProgressBarWidget


def megaupload(url, filename, callback=None,
                ETA2callback="auto", kbps=96, max_rate=None):
    """
    Given a megaupload URL gets the file

    Reproduce this :program:`wget` command::

       $ wget --save-cookies="mu" --load-cookies="mu" \
            -w 45 PUBLIC_MEGAUPLOAD_URL FILE_DIRECT_URL

    Arguments:
    url -- the URL to a megaupload content
    callback -- function to callback. It's useful to do something
                with the partially downloaded file. (i.e. play it)

    ETA2callback -- is the :abbr:`ETA (Estimated time to Arrival)` to
                    make the callback. Should be an :type:`int` (seconds).
                    The special value ``'auto'`` indicates that
                    the parameter will be estimated as ``file_size / kbps``

    kbps -- Kilobytes per seconds. It's a compression level factor. Needed if
            ``'auto'`` is given as ETA2callback
            A greater value means wait more before make the callback.
            ``95`` is a standard compression in cuevana.tv

    max_rate -- Max transfer rate in Kilobytes per seconds
                If None, no limit is apply.
    """

    if not url.startswith('http://www.megaupload.com/?d='):
        raise NotValidMegauploadLink

    cj = cookielib.CookieJar()
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cj) )

    p = pq(url=url, opener=lambda url: opener.open(url).read())
    url_file = p('a.down_butt1').attr('href')

    if not url_file:
        raise NotAvailableMegauploadContent

    msg = 'Downloading %s...' #if not callback else 'Buffering %s...'
    countdown(45,  msg % filename)
    try:
        response = opener.open(url_file)
        size = int(response.info().values()[0])
    except urllib2.HTTPError, e:
        print "Problem downloading... :("
    else:
        chunk = 4096
        if ETA2callback == "auto":
            ETA2callback = size / (kbps * 1024)
        my_eta = ETA_callback(ETA2callback, callback)

        widgets = ['', Percentage(), ' ', Bar('='),
                   ' ', my_eta, ' ',
                   LimitedFileTransferSpeed(max_rate=max_rate)]
        pbar = ProgressBar(widgets=widgets, maxval=size).start()
        with open(filename, 'wb') as localfile:
            copy_callback(response.fp, localfile, size, chunk,
                            lambda pos: pbar.update(pos),
                            lambda : pbar.finish())


def smart_urlretrieve(url, local, referer=''):
    """
    Analogous to urllib.urlretrieve,
    but could handle a referer and the cookies it sets

    .. versionadded:: 0.4.3
    """
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cj) )
    request = urllib2.Request(url)
    if referer:
        dummy = opener.open(referer).read()
        request.add_header('Referer', referer)
    response = opener.open(request)
    with open(local, 'wb') as localfile:
        shutil.copyfileobj(response.fp, localfile)

def countdown(seconds, msg="Done"):
    """
    Wait `seconds` counting down.  When it's done print `msg`
    """
    for i in range(seconds, 0, -1):
        sys.stdout.write("%02d" % i)
        time.sleep(1)
        sys.stdout.write("\b\b")
        sys.stdout.flush()
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def copy_callback(src, dest, src_size=None, chunk=10240,
                    callback_update=None, callback_end=None):
    """
    Copy a file calling back a function on each chunk and when finish
    """
    if not src_size:
        src_size = os.stat(src.name).st_size

    cursor = 0
    while True:
        buffer = src.read(chunk)
        if buffer:
            # ..if not, write the block and continue
            dest.write(buffer)
            if callback_update:
                status = callback_update(cursor)
                if status == 'cancel':
                    return
            cursor += chunk
        else:
            break

    if callback_end:
        callback_end()
    src.close()
    dest.close()

    # Check output file is same size as input one!
    dest_size = os.stat(dest.name).st_size
    if dest_size != src_size:
        raise IOError(
            "New file-size does not match original (src: %s, dest: %s)" % (
            src_size, dest_size)
        )


class ETA_callback(ETA):
    """ProgressBarWidget for the Estimated Time of Arrival that 
    call back a function when `seconds` or less left to arrival
    """
    def __init__(self, seconds=-1, callback=None):
        ETA.__init__(self)
        self._seconds = seconds
        self._callback = callback
        self._triggered = False

    def update(self, pbar):
        if pbar.currval == 0:
            return 'ETA:  --:--:--'
        elif pbar.finished:
            return 'Time: %s' % self.format_time(pbar.seconds_elapsed)
        else:
            elapsed = pbar.seconds_elapsed
            eta = elapsed * pbar.maxval / pbar.currval - elapsed
            if not self._triggered and eta <= self._seconds and self._callback:
                self._callback()
                self._triggered = True
            return 'ETA:  %s' % self.format_time(eta)


class LimitedFileTransferSpeed(ProgressBarWidget):
    """
    Widget for showing the transfer speed (useful for file transfers).
     It accepts an extra `max_rate` parameter (int in [kbps]) to limit
    (sleep) the download process when it is passed
    """

    def __init__(self, unit='B', max_rate=None):
        self.unit = unit
        self.fmt = '%6.2f %s'
        self.prefixes = ['', 'K', 'M', 'G', 'T', 'P']
        self.max_rate = max_rate

    def update(self, pbar):
        if pbar.seconds_elapsed < 2e-6:#== 0:
            bps = 0.0
        else:
            bps = pbar.currval / pbar.seconds_elapsed
            if self.max_rate:
                expected_time = pbar.currval / (float(self.max_rate) * 1024)
                sleep_time = expected_time - pbar.seconds_elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        spd = bps
        for u in self.prefixes:
            if spd < 1024:
                break
            spd /= 1024
        return self.fmt % (spd, u + self.unit + '/s')


def megaupload_gui(caller, url, filename, ETA2callback="auto",
                kbps=96, max_rate=None):
    """
    Given a megaupload URL gets the file

    Reproduce this :program:`wget` command::

       $ wget --save-cookies="mu" --load-cookies="mu" \
            -w 45 PUBLIC_MEGAUPLOAD_URL FILE_DIRECT_URL

    Arguments:
    sender -- the caller of this function. Used for sending signals to
              it (usually a thread)
    url -- the URL to a megaupload content

    ETA2callback -- is the :abbr:`ETA (Estimated time to Arrival)` to
                    make the callback. Should be an :type:`int` (seconds).
                    The special value ``'auto'`` indicates that
                    the parameter will be estimated as ``file_size / kbps``

    kbps -- Kilobytes per seconds. It's a compression level factor. Needed if
            ``'auto'`` is given as ETA2callback
            A greater value means wait more before make the callback.
            ``95`` is a standard compression in cuevana.tv

    max_rate -- Max transfer rate in Kilobytes per seconds
                If None, no limit is apply.
    """

    if not url.startswith('http://www.megaupload.com/?d='):
        raise NotValidMegauploadLink

    cj = cookielib.CookieJar()
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cj) )

    p = pq(url=url, opener=lambda url: opener.open(url).read())
    url_file = p('a.down_butt1').attr('href')

    if not url_file:
        raise NotAvailableMegauploadContent

    # Countdown for 45s
    for i in range(45, -1, -1):
        if caller._cancel:
            return
        update_gui_status(caller, 'Waiting %.2ds' % i, None, None, None, '--:--:--')
        time.sleep(1)

    try:
        response = opener.open(url_file)
        size = int(response.info().values()[0])
    except urllib2.HTTPError, e:
        update_gui_status(caller, 'Error downloading: %s' % e, None, None, None,
            None)
    else:
        chunk = 4096
        if ETA2callback == "auto":
            ETA2callback = size / (kbps * 1024)
        start_time = time.time()
        with open(filename, 'wb') as localfile:
            copy_callback(response.fp, localfile, size, chunk,
                            lambda pos: update_gui(caller, pos, size, ETA2callback,
                                        max_rate, start_time),
                            lambda : update_gui(caller=caller, size=size,
                                        start_time=start_time))
def update_gui_status(caller, *status):
    caller.update_download_status(status)

def update_gui(caller, pos=-1, size=-1, seconds=-1,
                max_rate=None, start_time=None):
    def format_time(seconds):
        return time.strftime('%H:%M:%S', time.gmtime(seconds))

    def get_speed():
        fmt = '%6.2f %s'
        prefixes = ['', 'K', 'M', 'G', 'T', 'P']
        elapsed = time.time() - start_time

        if elapsed < 2e-6:#== 0:
            bps = 0.0
        else:
            bps = pos / elapsed
            if max_rate:
                expected_time = pos / (float(max_rate) * 1024)
                sleep_time = expected_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        spd = bps
        for u in prefixes:
            if spd < 1024:
                break
            spd /= 1024
        return fmt % (spd, u + 'B/s')

    if caller._cancel:
        return 'cancel'

    speed = status = ' '
    _seconds = seconds

    if start_time:
        elapsed = time.time() - start_time

        if pos == 0:
            eta = '--:--:--'
        elif pos == -1:
            status = 'Finished'
            eta = 'Time: %s' % format_time(elapsed)
            pos = size
        else:
            status = 'Downloading'
            eta = elapsed * size / pos - elapsed
            if not caller._cb_triggered and eta <= _seconds:
                caller._cb_triggered = True
            speed = get_speed()
        update_gui_status(caller, status, size, pos, speed, format_time(eta) if status == 'Downloading' else eta)


class NotValidMegauploadLink(Exception):
    """This is not a valid MEGAUPLOAD link"""
    pass

class NotAvailableMegauploadContent(Exception):
    """The content for the link you provided isn't available"""
    pass
