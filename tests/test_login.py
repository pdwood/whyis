#from __future__ import print_function
#from future import standard_library
#standard_library.install_aliases()
from testcase import WhyisTestCase

from base64 import b64encode

from rdflib import *

import json
from io import StringIO

class LoginTest(WhyisTestCase):
    
    def test_plain_text_upload(self):
        user_details = self.create_user("user@example.com","password")
        print (user_details)
        self.assertEquals(user_details[0], 'user@example.com')
        user_obj = self.app.datastore.find_user(email='user@example.com')
        print(user_obj)
        self.assertNotEquals(user_obj, None)
        self.assertEquals('user@example.com', user_obj.email)
        login_response = self.login(*user_details)
        self.assertNotIn(b'USER = { }', login_response.data)
        #print(login_response.response)

