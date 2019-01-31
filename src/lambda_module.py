#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Automate Aurora new engine update notifications

A script, for lambda use, to check for new Aurora version releases
(since no notification is provided for non-mandatory releases) and notify via SES.

Architecture based/modeled on aws-cost-explorer-report by David Faulkner.
(https://github.com/aws-samples/aws-cost-explorer-report)
"""

import requests
import hashlib
import json
import os
import botocore
import AWSHelper
from bs4 import BeautifulSoup

# For email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

__author__ = "Paul (Hyung Yuel) Kim"
__credits__ = ["David Faulkner"]
__license__ = "MIT No Attribution"
__version__ = "0.1.0"

# GLOBALS
BUCKET = os.environ.get('BUCKET')  # Bucket for keeping previous sha1 hash results of the Aurora Engine updates doc.
LOGGER = AWSHelper.LOGGER


class CheckAuroraEngineUpdates(object):
    """
    Checks Aurora Documentation site for checking new Engine Update releases.
    """

    def __init__(self):
        # Setup config
        self.config = AWSHelper.load_config()

        # AWSHelper classes
        self.sts_helper = AWSHelper.STSHelper()
        self.org_helper = AWSHelper.OrganizationHelper()
        self.s3_helper = AWSHelper.S3Helper()
        self.ses_helper = AWSHelper.SESHelper()

        # Load Account Info
        self.account = self.get_aws_account_info()  # AWS Account info

        self.aurora20Doc = \
            'https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.Updates.20Updates.html'
        self.aurora11Doc = \
            'https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.Updates.11Updates.html'
        self.aurora20Digest = ''   # Sha1 digest of self.aurora20Doc
        self.aurora11Digest = ''  # Sha1 digest of self.aurora11Doc

        self.load_fingerprints()

    def get_aws_account_info(self) -> str:
        """
        Get the aws account number of the current user
        """

        account_id = self.sts_helper.get_account_id()
        account_info = self.org_helper.get_account_info(account_id)
        account = {'account_id': account_id}
        account.update(account_info)
        return account

    def load_fingerprints(self):
        """
        Load Aurora Doc fingerprints saved from last invocation.
        """

        file_name = self.account['account_id'] + ':' + self.account['account_name'] + \
                                                 ':' + 'Aurora_updates_doc_fingerprints.json'

        try:
            self.s3_helper.download_file(BUCKET, file_name, '/tmp/' + file_name)
            LOGGER.info('Downloading from ' + BUCKET + ', file ' + file_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                pass  # Ignore if the file doesn't already exist, this may be the first invocation

        # Retrieve the previous fingerprints
        try:
            with open('/tmp/' + file_name, 'r') as fin:
                data = fin.read()
                fingerprints_from_file = json.loads(data)
                LOGGER.info('Fingerprints from file: ')
                LOGGER.info(fingerprints_from_file)

                self.aurora11Digest = fingerprints_from_file['11']
                self.aurora20Digest = fingerprints_from_file['20']

        except FileNotFoundError:
            pass  # Ignore if the file doesn't already exist, this may be the first invocation

    def save_fingerprints(self):
        """
        Save the doc11 and doc20 site sha1 digest for comparison in later invocations.
        """
        file_name = self.account['account_id'] + ':' + self.account[
            'account_name'] + ':' + 'Aurora_updates_doc_fingerprints.json'

        # Save the updated fingerprint
        with open('/tmp/' + file_name, 'w') as fout:
            fingerprints = {'11': self.aurora11Digest, '20': self.aurora20Digest}
            json.dump(fingerprints, fout)

        self.s3_helper.upload_file(BUCKET, '/tmp/' + file_name, file_name)

    def send_email(self, update11=False, update20=False):
        """
        Send Aurora engine update email notification through SES
        """
        if self.config['ses_region']:
            msg = MIMEMultipart()
            msg['From'] = str(self.config['ses_from'])
            msg['To'] = ', '.join(str(self.config['ses_send']).split(','))
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = 'automate-auroraNewVersionChecking has found new Aurora updates.'

            update11_text = 'Amazon Aurora MySQL 1.1 Database Engine Updates found: ' + self.aurora11Doc
            update20_text = 'Amazon Aurora MySQL 2.0 Database Engine Updates found: ' + self.aurora20Doc

            # Customize email template when no support case has been opened
            if update11 and update20:
                text = self.config['email_template'].format(update11_text, update20_text)
            elif update11:
                text = self.config['email_template'].format(update11_text)
            elif update20:
                self.config['email_template'].format(update20_text)

            msg.attach(MIMEText(text))

            result = self.ses_helper.send_raw_email(msg['From'], msg['To'], msg,
                                                    region=str(self.config['ses_region']))
            LOGGER.info('Email sent. MessageId: ' + result['MessageId'])

    def check_version_updates(self, version='20', test='False') -> bool:
        """
        Check for updated versions of the Aurora Engine
        """

        new_version = False  # Flag to return indicating new Aurora engine update

        if test == 'True':
            # Test with locally saved files for test run when this Lambda module is called with
            # {
            #   "test": "False"
            # }
            # event context.
            if version == '20':
                with open('test20.htm', 'r') as fin:
                    data = fin.read()
                    data = data.encode('utf-8')
                    if self.aurora20Digest != hashlib.sha1(data).hexdigest():
                        self.aurora20Digest = hashlib.sha1(data).hexdigest()
                        new_version = True
            else:
                with open('test11.htm', 'r') as fin:
                    data = fin.read()
                    data = data.encode('utf-8')
                    if self.aurora11Digest != hashlib.sha1(data).hexdigest():
                        self.aurora11Digest = hashlib.sha1(data).hexdigest()
                        new_version = True
        else:
            if version == '20':
                page = requests.get(self.aurora20Doc)
            else:
                page = requests.get(self.aurora11Doc)

            if page.status_code != 200:
                raise Exception('lambda_module.py exited with error: ' + str(page.status_code))

            soup = BeautifulSoup(page.text, 'html.parser')
            updates = soup.find('div', {'id': 'main-col-body'})  # Extract Aurora Updates text portion

            if version == '20':
                if self.aurora20Digest != hashlib.sha1(updates.text.encode('utf-8')).hexdigest():
                    self.aurora20Digest = hashlib.sha1(updates.text.encode('utf-8')).hexdigest()
                    new_version = True
            else:
                if self.aurora11Digest != hashlib.sha1(updates.text.encode('utf-8')).hexdigest():
                    self.aurora11Digest = hashlib.sha1(updates.text.encode('utf-8')).hexdigest()
                    new_version = True

        if version == '20':
            LOGGER.info('Aurora20 Doc Digest: ' + self.aurora20Digest)
        else:
            LOGGER.info('Aurora11 Doc Digest: ' + self.aurora11Digest)

        return new_version


def main_handler(event=None, context=None):
    check = CheckAuroraEngineUpdates()

    try:
        test_flag = event['test']
    except:
        test_flag = 'False'
    update20 = check.check_version_updates(test=test_flag)
    update11 = check.check_version_updates(version='11', test=test_flag)

    # Send email
    if update11 or update20:  # Only send email when we have found new Aurora update.
        check.send_email(update11, update20)
        LOGGER.info('Aurora update found. \nVersion1.1: ' + str(update11) + '\nVersion2.0: ' + str(update20))
    else:
        LOGGER.info('No Aurora update found.\n')

    # Save the fingerprints for comparison in subsequent invocations.
    check.save_fingerprints()

    return 0


if __name__ == '__main__':
    main_handler()
