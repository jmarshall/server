"""
Performs a request via the client with OpenID Connect enabled,
with a local OP server.
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import requests
import subprocess
from lxml import html
from urlparse import urlparse

import client
import server
import server_test


def getClientKey(server_url, username, password):
    """
    This function automatically performs the steps that the user would usually
    perform manually in order to obtain a token.
    """
    session = requests.session()
    # Load the login page (this request includes the redirect to the OP)
    loginPage = session.get("{}/".format(server_url), verify=False)
    # Extract the state data from the login form
    loginTree = html.fromstring(loginPage.text)
    inputTags = loginTree.iterdescendants('input')
    state = (tag for tag in inputTags if tag.name == 'state').next().value
    # Submit the form data to the OP for verification (if verification is
    # successful, the request will redirect to a page with the key)
    data = {
        'username': username,
        'password': password,
        'state': state
    }
    opLocation = urlparse(loginPage.url).netloc
    nextUrl = 'https://{}/user_pass/verify'.format(opLocation)
    keyPage = session.post(nextUrl, data, verify=False)
    # Extract the key from the page
    keyTree = html.fromstring(keyPage.text)
    tokenMarker = 'Session Token '  # the token always appears after this text
    tokenTag = (tag for tag in keyTree.iterdescendants()
                if tag.text_content().startswith(tokenMarker)).next()
    return tokenTag.text_content()[len(tokenMarker):]


class TestOidc(server_test.ServerTestClass):
    """
    Tests the oidc flow
    """
    @classmethod
    def otherSetup(cls):
        cls.simulatedVariantSetId = "c2ltdWxhdGVkRGF0YXNldDA6c2ltVnMw"
        requests.packages.urllib3.disable_warnings()
        cls.opServer = server.OidcOpServerForTesting()
        cls.opServer.start()

    @classmethod
    def otherTeardown(cls):
        cls.opServer.shutdown()

    @classmethod
    def getServer(cls):
        return server.Ga4ghServerForTesting(useOidc=True)

    def testOidc(self):
        serverUrl = self.server.getUrl()
        key = getClientKey(serverUrl, 'diana', 'krall')
        test_client = client.ClientForTesting(
            serverUrl, flags="--key {}".format(key))
        self.runVariantsRequest(test_client)
        test_client.cleanup()

    def testOidcBadLoginPassword(self):
        serverUrl = self.server.getUrl()
        with self.assertRaises(StopIteration):
            getClientKey(serverUrl, 'diana', 'krallxxx')

    def testOidcBadLoginKey(self):
        serverUrl = self.server.getUrl()
        test_client = client.ClientForTesting(
            serverUrl, flags="--key {}".format('ABC'))
        with self.assertRaises(subprocess.CalledProcessError):
            test_client.runCommand(
                "variants-search -s 0 -e 2 -V {}".format(
                    self.simulatedVariantSetId),
                debugOnFail=False)
        test_client.cleanup()

    def testMultipleOidcClients(self):
        serverUrl = self.server.getUrl()
        key = getClientKey(serverUrl, 'diana', 'krall')
        key2 = getClientKey(serverUrl, 'upper', 'crust')
        client1 = client.ClientForTesting(
            serverUrl, flags="--key {}".format(key))
        client2 = client.ClientForTesting(
            serverUrl, flags="--key {}".format(key2))
        self.runVariantsRequest(client1)
        self.runVariantsRequest(client2)
        client1.cleanup()
        client2.cleanup()

    def runVariantsRequest(self, client):
        self.runClientCmd(
            client,
            "variants-search -s 0 -e 2 -V {}".format(
                self.simulatedVariantSetId))
