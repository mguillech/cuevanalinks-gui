#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import urllib
import random
import imghdr
from StringIO import StringIO
import unittest2 as unittest

from mock import Mock

from cuevanalinks import cuevanaapi as api
from cuevanalinks.downloaders import smart_urlretrieve
from cuevanalinks.utils import get_numbers

TEST_LOCALLY = True #False
FORCE_UPDATE = False

local_dir = os.path.join(os.path.dirname( os.path.abspath (__file__)), 'local')
just_updated = []   #track updated files to retrieve them once


class HelperLocal(object):
    def pyquery_local(self, *args, **kwargs):
        filename = self.cuevanaURL2filename(args[0])
        if filename:
            args = args[1:] if len(args) > 0 else ()
            return self.real_pq(*args,filename=filename,**kwargs)
        else:
            return self.real_pq(*args,**kwargs)

    def source_get_simulator(self, *args, **kwargs):
        expected_url = api.URL_BASE + api.SOURCE_GET
        host, key = [v.split('=')[1] for v in args[1].split('&')]
        if args[0] == expected_url and \
           host in ('megaupload', 'bitshare', 'filefactory', 'hotfile') \
           and len(key) == 32:
            return StringIO('valid url for %s' % host)
        else:
            return StringIO('unknow %s %s %s' % (args[0], host, key) )

    def get_subtitle_lines(self, url, referer):
        filename = self.cuevanaURL2filename(url, referer)
        return open(filename, 'r').readlines(1024)
    

    def cuevanaURL2filename(self, url, referer=''):
        """
        given a URL from cuevana, return the path to a local version 
        if this doesn't exist or FORCE_UPDATE is true the file 
        is retrieved once
        """
        if isinstance(url, basestring) and url.startswith(api.URL_BASE):
            filename = url.replace(api.URL_BASE,'') \
                          .replace('/', '_') \
                          .replace('?', '-') \
                          .replace('&', '-') 
            filename = os.path.join(local_dir, filename)
            if (FORCE_UPDATE and filename not in just_updated) or \
               not os.path.exists(filename) :            
               
                if referer:
                    smart_urlretrieve(url, filename, referer)
                else:
                    urllib.urlretrieve(url, filename)
                just_updated.append(filename)
                print "%s was retrieved into %s" % (url, filename)
            return filename



class TestAPI(unittest.TestCase, HelperLocal):
    
    def setUp(self):
        if TEST_LOCALLY:
            self.real_pq = api.pq
            api.pq = Mock(side_effect=self.pyquery_local)
        self.api = api.CuevanaAPI()

    def tearDown(self):
        if TEST_LOCALLY:
            api.pq = self.real_pq
    
    def test_get_show_return_show(self):  
        self.bigbang = self.api.get_show('big bang')
        self.assertEqual(type(self.bigbang), api.Show)
        self.assertEqual(self.bigbang.title, 'The Big Bang Theory')
    
        
    def test_get_show_return_none(self):  
        self.non_existent = self.api.get_show('a non existent show')
        self.assertEqual(self.non_existent, None)
    
    def test_get_show_return_all(self):
        self.many_shows = self.api.get_show('al', return_all=True)
        self.assertTrue(len(self.many_shows) > 1)
        for show in self.many_shows:
            self.assertTrue('Al' in show.title)
    
    def test_search_by_title(self):
        self.matrix_saga = self.api.search('matrix')
        for matrix in self.matrix_saga:
            self.assertTrue('Matrix' in matrix.title)
    
    def test_search_return_none(self):
        self.non_existent = self.api.search('a non existent content')
        self.assertEqual(self.non_existent, None)

    def test_search_not_valid_category(self):
        self.assertRaises(api.NotValidSearchCategory, self.api.search, 
                          u'Charly García', cat='music')
        
    def test_search_by_director(self):
        self.bielinsky_films = self.api.search(u'bielinsky', cat='director')
        for film in self.bielinsky_films:
            self.assertEqual( film.director, [u'Fabián Bielinsky'])
    
    def test_search_by_actor(self):
        self.results = self.api.search('alexandre rodrigues', cat='actor')
        for film in self.results:
            self.assertIn( 'Alexandre Rodrigues', film.cast)
            
    def test_search_by_actor(self):
        self.results = self.api.search('alexandre rodrigues', cat='actor')
        for film in self.results:
            self.assertIn( 'Alexandre Rodrigues', film.cast)
    
    def test_search_by_episode(self):
        self.results = self.api.search('Hamsterdam', cat='episode')
        for episode in self.results:
            self.assertIsInstance(episode, api.Episode)
            self.assert_('Hamsterdam' in episode.title)
            
    def test_rss_movies(self):
        rss_movies = self.api.rss_movies()
        self.assertGreater(len(rss_movies), 0)
        for film in rss_movies:
            self.assertIsInstance(film, api.Movie)

    def test_rss_series(self):
        rss_series = self.api.rss_series()
        self.assertGreater(len(rss_series), 0)
        for episode in rss_series:
            self.assertIsInstance(episode, api.Episode)

    def test_load_pickle_raises_except_when_malformed(self):
        self.assertRaises(ValueError, self.api.load_pickle, 'dsfkjs')
    
    def _test_load_pickle(self, url, populated):
        content = api.dispatch(url)
        if populated:
            dummy = content.title     #just to get all properties populated
        content_pickled = content.get_pickle()
        content_unpickled = self.api.load_pickle(content_pickled)

        #same type and same attributes
        self.assertEqual(type(content), type(content_unpickled))
        
        unpickled_vars = vars(content_unpickled)
        for k, v in vars(content).iteritems():
            self.assertEqual(v, unpickled_vars[k])

    def test_load_pickle_movie_populated(self):
        url = 'http://www.cuevana.tv/peliculas/71/nueve-reinas/'
        self._test_load_pickle(url, True)
    
    def test_load_pickle_movie_not_populated(self):
        url = 'http://www.cuevana.tv/peliculas/71/nueve-reinas/'
        self._test_load_pickle(url, False)

    def test_load_pickle_episode_populated(self):
        url = 'http://www.cuevana.tv/series/285/the-big-bang-theory/pilot/' 
        self._test_load_pickle(url, True)
    
    def test_load_pickle_episode_not_populated(self):
        url = 'http://www.cuevana.tv/series/285/the-big-bang-theory/pilot/' 
        self._test_load_pickle(url, False)
    
    def test_load_pickle_show_populated(self):
        url = 'http://www.cuevana.tv/series/68/dummy' #Big Bang Theory
        self._test_load_pickle(url, True)
    
    def test_load_pickle_show_not_populated(self):
        url = 'http://www.cuevana.tv/series/68/dummy' #Big Bang Theory
        self._test_load_pickle(url, False)
    
class BaseTestContent(HelperLocal):
    
    def setUp(self):
        if TEST_LOCALLY:
            self.real_pq = api.pq
            self.real_urlopen = api.urllib.urlopen
            api.urllib.urlopen = Mock(side_effect=self.source_get_simulator)
            api.pq = Mock(side_effect=self.pyquery_local)
        
        self.content = api.dispatch(self.content_url)

    def tearDown(self):
        if TEST_LOCALLY:
            api.pq = self.real_pq
            api.urllib.urlopen = self.real_urlopen 
    
    def test_general_properties(self):
        for k, v in self.properties.iteritems():
            self.assertEqual( getattr(self.content, k), v)
            
    
    def test_strings(self):
        self.assertEqual(unicode(self.content), self.unicode_string)
        self.assertEqual(repr(self.content), unicode(self.content))
    
    
    def test_pretty_title(self):
        self.assertEqual(self.content.pretty_title, self.pretty_title )
    
    
    def test_plot(self):
        self.assert_(self.content.plot.startswith(self.plot_starts))
    
    def test_url(self):
        self.assertEqual(self.content.url, self.content_url)
    
    def test_cid(self):
        self.assertEqual(self.content.cid, self.cid)
    
    def test_sources(self):        
        sources = self.content.sources
        for source in sources:
            self.assert_(source.startswith('valid url'))
    
    def test_get_links(self):
        m = self.content
        lines = m.get_links().split('\n')
        self.assertEqual(m.pretty_title, lines[0])
        self.assertEqual(len(m.pretty_title), len(lines[1]))
        self.assert_( set(m.sources).issubset(set(lines)) )
            
    def test_subs(self):
        for sub_url in self.content.subs.values():
            sub_lines = self.get_subtitle_lines(sub_url, self.content.url)
            self.assertEqual('1', sub_lines[0].strip())
            self.assertIn('-->', sub_lines[1])
            self.assertIn(self.first_sub_line, sub_lines[2])
    
    def test_filename_default(self):
        self.assertEqual(self.content.filename(), self.filename)
    
    def test_filename_short(self):
        self.assertEqual(self.content.filename('short'), self.filename_short)
    
    def test_filename_other_extension(self):
        ext = ''.join([chr(random.randrange(97,123)) for v in range(3)])
        self.assert_(self.content.filename(extension=ext).endswith(ext))
    
    def test_thumbnail(self):
        image = self.cuevanaURL2filename(self.content.thumbnail)
        self.assertEqual(imghdr.what(image), 'jpeg')


class TestMovie_1(BaseTestContent, unittest.TestCase): 
    content_url = 'http://www.cuevana.tv/peliculas/997/the-godfather/'
    unicode_string = '<Movie: The Godfather>'
    cid = 997
    title = 'The Godfather'
    plot_starts = 'Don Vito Corleone es el jefe'
    pretty_title = 'The Godfather (1972)'
    filename = 'The Godfather (1972).srt'
    filename_short = 'TheGodfather.srt'
    first_sub_line = 'Mario Puzo'    
    properties = {'year': 1972, 
                 'gender': 'Drama', 
                 'director': ['Francis Ford Coppola'],
                 'script': ['Francis Ford Coppola', 'Mario Puzo'], 
                 'duration': '175 min', 
                 'producer': 'Paramount Pictures / Albert S. Ruddy Production', #the maffia
                 'cast': ['Marlon Brando', 'Al Pacino', 'James Caan', 
                          'Robert Duvall', 'Diane Keaton', 'John Cazale', 
                          'Talia Shire', 'Richard Castellano', 'Sterling Hayden', 
                          'Gianni Russo', 'Rudy Bond', 'John Marley', 
                          'Richard Conte', 'Al Lettieri', 'Abe Vigoda'],
                 }

class TestMovie_2(BaseTestContent, unittest.TestCase): 
    content_url = 'http://www.cuevana.tv/peliculas/1076/amores-perros/'
    unicode_string = '<Movie: Amores Perros>'
    cid = 1076
    title = 'Amores Perros'
    plot_starts = u'Ciudad de México, un fatal accidente automovilístico'
    pretty_title = 'Amores Perros (2000)'
    filename = 'Amores Perros (2000).srt'
    filename_short = 'AmoresPerros.srt'
    first_sub_line = None
    properties = {'year': 2000, 
                 'gender': 'Drama', 
                 'director': [u'Alejandro González Iñárritu'],
                 'script': [u'Guillermo Arriaga Jordán'], 
                 'duration': '150 min', 
                 'producer': 'Altavista Films / Zeta Film', 
                 'cast': [u'Emilio Echevarría', u'Gael García Bernal', 
                          u'Goya Toledo', u'Álvaro Guerrero', 
                          u'Vanessa Bauche', u'Jorge Salinas', 
                          u'Marco Pérez', 'Rodrigo Murray', 
                          u'Humberto Busto', u'Gerardo Campbell', 
                          u'Rosa María Bianchi', u'Dunia Saldívar', 
                          u'Adriana Barraza', u'José Sefami', 
                          'Patricio Castillo', 'Lourdes'],
                 }
    
class BaseTestEpisode(BaseTestContent):
    def test_show_title(self):
        self.assertEqual(self.content.show, self.show)
    
    def test_season(self):
        self.assertEqual(self.content.season, self.season)

    def test_episode(self):
        self.assertEqual(self.content.episode, self.episode)
        
    def test_next(self):
        next = self.content.next
        self.assertEqual(next.title, self.next_episode_title)
        
    def test_previous(self):
        previous = self.content.previous
        self.assertEqual(previous.title, self.previous_episode_title)
        

class TestEpisode_1(BaseTestEpisode, unittest.TestCase): 
    content_url = 'http://www.cuevana.tv/series/3309/the-wire/hamsterdam/'
    season, episode = 3, 4
    unicode_string = '<Episode: S03E04>'
    title = 'Hamsterdam'
    show = 'The Wire'
    next_episode_title = 'Straight and True'
    previous_episode_title = 'Dead Soldiers'
    cid = 3309
    sid = 910
    pretty_title = 'The Wire (S03E04) - Hamsterdam (2002)'
    plot_starts = u'Agentes y miembros del concejo municipal se reunen con residentes de Baltimore'
    filename = 'The Wire S03E04 - Hamsterdam (2002).srt'
    filename_short = 'TheWire3x04.srt'
    first_sub_line = 'apreciamos su aporte'
    properties = {'year': 2002,
                 'gender': 'Crimen',
                 'director': [u'David Simon (Creator)', 
                               'Ernest R. Dickerson', 'Joe Chappelle', 
                               'Edward Bianchi', 'Steve Shill', 
                               'Timothy Van'],
                 'script': [u'David Simon', u'Edward Burns', 
                            u'George Pelecanos', u'Richard Price', 
                            u'Dennis Lehane', u'Rafael Álvarez', 
                            'Joy Lusco'], 
                 'producer': 'HBO', 
                 'cast': ['Dominic West', 'John Doman', 'Idris Elba', 
                          'Frankie Faison', 'Larry Gilliard Jr.', 
                          'Wood Harris', 'Deirdre Lovejoy', 
                          'Wendell Pierce', 'Lance Reddick', 
                          'Andre Royo', 'Sonja Sohn', 'Aidan Gillen', 
                          'Clarke Peters', 'Robert Wisdom', 
                          'Seth Gilliam', 'Domenick Lombardozzi'],
                 }
                 
class Test_next_prev(HelperLocal, unittest.TestCase):
    def setUp(self):
        if TEST_LOCALLY:
            self.real_pq = api.pq
            self.real_urlopen = api.urllib.urlopen
            api.urllib.urlopen = Mock(side_effect=self.source_get_simulator)
            api.pq = Mock(side_effect=self.pyquery_local)
        
        self.the_wire = api.dispatch('http://www.cuevana.tv/series/910/the-wire/')

    def tearDown(self):
        if TEST_LOCALLY:
            api.pq = self.real_pq
            api.urllib.urlopen = self.real_urlopen 

    def test_next_last_of_a_season(self):
        last = self.the_wire.seasons[0][-1]
        next = last.next
        self.assertIsInstance(next, api.Episode)
        self.assertEqual(next.season, 2)
        self.assertEqual(next.episode, 1)
        
    def test_next_last_of_last_season(self):
        last = self.the_wire.seasons[-1][-1]
        next = last.next
        self.assertEqual(next, None)
    
    def test_prev_first_of_a_season(self):
        first = self.the_wire.seasons[1][0]
        prev = first.previous
        self.assertIsInstance(prev, api.Episode)
        self.assertEqual(prev.season, 1)
        self.assertEqual(prev.episode, 13)
        
    def test_next_last_of_last_season(self):
        first = self.the_wire.seasons[0][0]
        prev = first.previous
        self.assertEqual(prev, None)

class BaseTestShow(HelperLocal):
    def setUp(self):
        if TEST_LOCALLY:
            self.real_pq = api.pq
            api.pq = Mock(side_effect=self.pyquery_local)
        self.show = api.dispatch(self.show_url)

    def tearDown(self):
        if TEST_LOCALLY:
            api.pq = self.real_pq
    

    def test_strings(self):
        self.assertEqual(unicode(self.show), self.unicode_string)
        self.assertEqual(repr(self.show), unicode(self.show))
            
    def test_plot(self):
        self.assertIn(self.plot_has, self.show.plot)
    
    def test_url(self):
        self.assertEqual(self.show.url, self.show_url)

    def test_season(self):
        seasons = self.show.seasons
        self.assertEqual(len(seasons), len(self.seasons_length))
        for num, season in enumerate(seasons):
            self.assertEqual(len(season), self.seasons_length[num])
            for episode in season:
                self.assertEqual(type(episode), api.Episode)
                
    def test_get_season(self):
        for i in range(1, len(self.seasons_length) + 1):
            season = self.show.get_season(i)
            self.assertEqual(season, self.show.seasons[i - 1])
                
    def test_get_episodes_specific(self):
        season = 1
        for i in range(1, self.seasons_length[season - 1]):
            ep = self.show.get_episodes('s%02de%02d' % (season, i))
            self.assertEqual(len(ep), 1)
            self.assertEqual(type(ep[0]), api.Episode)
            self.assertEqual(ep[0].season, season)
            self.assertEqual(ep[0].episode, i)
    
    def test_get_episodes_a_whole_season(self):
        for s in range(1, len(self.seasons_length) + 1):
            episodes = self.show.get_episodes(s)
            self.assertEqual(len(episodes), self.seasons_length[s - 1])
            for ep in episodes:
                self.assertEqual(type(ep), api.Episode)
            episodes_str = self.show.get_episodes('s0' + str(s))
            self.assertEqual(episodes, episodes_str)
            
    def test_get_episodes_start_out_limits(self):
        start = ('s0', len(self.seasons_length) + 1)
        for s in start:
            self.assertRaises(api.UnavailableError, self.show.get_episodes, s)
        
    def test_get_episodes_end_greater_than_start(self):
        start = (2, len(self.seasons_length))
        for s in start:
            end = s - 1
            self.assertRaises(api.UnavailableError, self.show.get_episodes, s, end)
        
    def test_get_episodes_start_out_of_season(self):
        """
        tests for Unavailable start episode
        """
        for season, last_episode in enumerate(self.seasons_length):
            greater = 's%02de%02d' % (season + 1, last_episode + 1) #greater than last of the season
            lower = 's%02de%02d' % (season + 1, 0)
            self.assertRaises(api.UnavailableError, self.show.get_episodes, greater)
            self.assertRaises(api.UnavailableError, self.show.get_episodes, lower)
            
    def test_get_episodes_end_out_of_season(self):
        """
        tests for Unavailable end episode
        """
        for season, last_episode in enumerate(self.seasons_length):
            greater = 's%02de%02d' % (season + 1, last_episode + 1) #greater than last of the season
            lower = 's%02de%02d' % (season + 1, 0)
            self.assertRaises(api.UnavailableError, self.show.get_episodes, 's01e01', greater)
            self.assertRaises(api.UnavailableError, self.show.get_episodes, 's01e01', lower)
    
    def test_get_episodes_not_numbers(self):
        """
        tests when can't decode slices
        """
        self.assertRaises(api.UnavailableError, self.show.get_episodes, 'lala')
        self.assertRaises(api.UnavailableError, self.show.get_episodes, 'buuh', 'blah')
        self.assertRaises(api.UnavailableError, self.show.get_episodes, 's01', 'ouch')
        self.assertRaises(api.UnavailableError, self.show.get_episodes, 'wow', 's03')
    
    def _test_valid_slice(self, start, end, expected_len):
        numbers_start = get_numbers(start)
        numbers_end = numbers_start[:] if end == '' else get_numbers(end) 
        if len(numbers_start) == 1:
            numbers_start.append(1)
        if len(numbers_end) == 1:
            numbers_end.append(self.seasons_length[numbers_end[0] - 1])
        
        the_slice = self.show.get_episodes(start, end)
        
        #both start and end episode are included
        self.assertEqual(the_slice[0].season, numbers_start[0])
        self.assertEqual(the_slice[0].episode, numbers_start[1])
        self.assertEqual(the_slice[-1].season, numbers_end[0])
        self.assertEqual(the_slice[-1].episode, numbers_end[1])
        
        #TODO this should be automatic ;-)
        self.assertEqual(len(the_slice), expected_len)
        
    def test_valid_slice_0(self):
        self._test_valid_slice('s01', '', self.seasons_length[0])
    
    def test_valid_slice_1(self):
        self._test_valid_slice('s01e01', 's01e03', 3)
        
    def test_valid_slice_2(self):
        self._test_valid_slice('s01e01', 's02e01', self.seasons_length[0] + 1)
        
    def test_valid_slice_3(self):
        self._test_valid_slice('s02e04', 's03', self.seasons_length[1] + self.seasons_length[2] - 3)
        
    def test_valid_slice_4(self):
        self._test_valid_slice('s03', '5x9', self.seasons_length[2] + self.seasons_length[3] + 9)
            
    def test_valid_slice_5(self):
        self._test_valid_slice('s05', 's05', self.seasons_length[4])

    def test_valid_slice_6(self):
        self._test_valid_slice('s03', 's05', sum(self.seasons_length[2:]))
    
    def test_valid_slice_7(self):
        self._test_valid_slice('s01e01', 's01e' + str(self.seasons_length[0]), self.seasons_length[0])
    
    def test_valid_slice_8(self):
        self._test_valid_slice('s01', '%dx%s' % (len(self.seasons_length), self.seasons_length[-1]), sum(self.seasons_length))
            
class TestTheWire(BaseTestShow, unittest.TestCase):
    show_url = 'http://www.cuevana.tv/series/910/the-wire/'
    unicode_string = u'<Show: The Wire>'
    title = 'The Wire'
    sid = 910
    seasons_length = (13, 12, 12, 13, 10)
    plot_has = u'Aclamada serie que narra la investigación de un '\
                'asesinato con implicaciones de asuntos de drogas '\
                'en los barrios bajos de la ciudad de Baltimore'

class TestDexter(BaseTestShow, unittest.TestCase):
    show_url = 'http://www.cuevana.tv/series/115/dexter/'
    unicode_string = u'<Show: Dexter>'
    title = 'Dexter'
    sid = 115
    seasons_length = [12] * 5
    plot_has = u'Basada en la novela de Jeff Lindsay'


    

if __name__ == '__main__':    
	unittest.main()
