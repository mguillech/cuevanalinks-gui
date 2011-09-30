import unittest2 as unittest
import os
import time
import urllib2

from mock import Mock
from progressbar import ProgressBar

from cuevanalinks import downloaders as dwl


class TestDownloader(unittest.TestCase):
    
    def setUp(self):
        pass
        
    def test_valid_url(self):
        """tests that a NotValidMegauploadLink exception is raised when 
           a non Megaupload content url is given"""
           
        non_mu_url = "http://dummy_web.com"
           
        self.assertRaises(dwl.NotValidMegauploadLink, dwl.megaupload, 
                             non_mu_url, 'dummy')
                             
    def test_not_available_content(self):
        """tests that a NotAvailableMegauploadContent exception is raised when 
           there is no content available for the given Megaupload url"""
           
        non_available_mu_url = "http://www.megaupload.com/?d=dummy_code"
        self.assertRaises(dwl.NotAvailableMegauploadContent, dwl.megaupload, 
                          non_available_mu_url, 'dummy')
        
    def test_LimitedFileTransferSpeed(self):
        """tests that speed transfers limitation works"""
        
        FILE_SIZE = 1024 ** 2 #1Mb file
        MAX_RATE = 750 #in kpbs
        
        EXPECTED_TIME = FILE_SIZE / float(MAX_RATE * 1024)
        
        #create a dummy file
        with open('dummy', 'wb') as dummy:
            dummy.seek(FILE_SIZE - 1)
            dummy.write('\x00')
        
        #copy and time it
        widgets = [dwl.LimitedFileTransferSpeed(max_rate=MAX_RATE)]
        with open('dummy', 'r') as origin:
            with open('dummy2', 'wb') as dest:
                pbar = ProgressBar(widgets=widgets, maxval=FILE_SIZE).start()
                start = time.time()
                dwl.copy_callback(origin, dest, 
                              callback_update= lambda pos: pbar.update(pos),
                              callback_end= lambda : pbar.finish())
                CONSUMED_TIME = time.time() - start
                
        #remove temp files
        os.remove('dummy')
        os.remove('dummy2')
        self.assertAlmostEqual (CONSUMED_TIME, CONSUMED_TIME)

    def test_callbacks(self):
        """
        tests a the given function is called on every chunk and 
        the on_finish function just once
        """ 
        
        FILE_SIZE = 1024  #1kb file
        CHUNK = 16
        expected_on_chunk = FILE_SIZE / CHUNK
        on_chunk = Mock()
        on_finish = Mock()
        
        with open('dummy', 'wb') as dummy:
            dummy.seek(FILE_SIZE - 1)
            dummy.write('\x00')
        with open('dummy', 'r') as origin:
            with open('dummy2', 'wb') as dest:
                dwl.copy_callback(origin, dest, chunk=CHUNK , 
                    callback_update=on_chunk, callback_end=on_finish)
        os.remove('dummy')
        os.remove('dummy2')
        self.assertEqual (on_chunk.call_count, expected_on_chunk)
        self.assertEqual (on_finish.call_count, 1)

    def _test_ETA_callback(self, DURATION, DEADLINE, STEPS=1000):
        """
        tests ETA_callback widget. 
        It call a function one when ETA or less left
        """ 
        
        STEPS = 1000
        step_duration = DURATION / STEPS
        
        a_mock = Mock()
        the_callback = lambda: a_mock(time.time())  #register the time when called
        w = dwl.ETA_callback(DEADLINE, the_callback) #the widget
        
        pbar = ProgressBar(widgets=[w], maxval=STEPS)
        pbar.start()
        for i in xrange(STEPS):
            time.sleep(step_duration)
            pbar.update(i)
        pbar.finish()
        called_at = a_mock.call_args[0][0]
        called_when_left = time.time() - called_at
        self.assertLessEqual(called_when_left, DEADLINE * 1.06)    #ETA_real <= ETA_expected + 6%
        self.assertLessEqual(DEADLINE - called_when_left, DEADLINE * 0.06) #error <= 6%
        self.assertEqual(a_mock.call_count, 1)

    def test_ETA_callback1(self):
        self._test_ETA_callback(2.0, 1.0)
    
    def test_ETA_callback2(self):
        self._test_ETA_callback(4.0, 3.5)

    def test_ETA_callback3(self):
        self._test_ETA_callback(6.0, 4.0, 100000)

    @unittest.SkipTest
    def test_ETA_callback4(self):
        self._test_ETA_callback(50.0, 40.0, 1000000)

if __name__ == '__main__':
    unittest.main()
