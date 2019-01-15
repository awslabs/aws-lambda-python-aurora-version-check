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
Helper module for 'Aurora Engine Update notification automation'
"""

import boto3
from typing import Mapping
import os
import logging.config
from shutil import copyfile
import yaml

__author__ = "Paul (Hyung Yuel) Kim"
__license__ = "MIT No Attribution"
__version__ = "0.1.0"

# GLOBALS
CONFIG_BUCKET = os.environ.get('CONFIG_BUCKET')
CONFIG_FILE = os.environ.get('CONFIG_FILE')
LOGGER = logging.getLogger(__name__)


class BaseLogger(object):
    """
    base class to get logger object
    """
    def __init__(self):
        # Setup logger
        self.logger = LOGGER


class OrganizationHelper(BaseLogger):
    """
    EC2 Helper class.
    """

    def get_account_info(self, account_id: str) -> Mapping[str, str]:
        self.logger.debug('Querying AWS account name and email info')
        org = boto3.client('organizations')
        account_name = org.describe_account(AccountId=account_id).get('Account').get('Name')
        account_email = org.describe_account(AccountId=account_id).get('Account').get('Email')
        account_info = {'account_name': account_name, 'account_email': account_email}
        return account_info


class STSHelper(BaseLogger):
    """
    EC2 Helper class.
    """

    def get_account_id(self) -> str:
        client = boto3.client("sts")

        self.logger.debug('Querying current AWS Account ID')
        return client.get_caller_identity()["Account"]


class S3Helper(BaseLogger):
    """
    S3 Helper class.
    """

    def upload_file(self, bucket, local_filename, remote_filename, region=None, enable_logging=True):
        if enable_logging:
            self.logger.debug('Uploading ' + local_filename + ' to ' + bucket + '/' + remote_filename)

        if region:
            s3 = boto3.client('s3', region_name=region)
        else:
            s3 = boto3.client('s3')

        s3.upload_file(local_filename, bucket, remote_filename)

    def download_file(self, bucket, remote_filename, local_filename, region=None, enable_logging=True):
        if enable_logging:
            self.logger.debug('Downloading ' + local_filename + ' to ' + bucket + '/' + remote_filename)

        if region:
            s3 = boto3.client('s3', region_name=region)
        else:
            s3 = boto3.client('s3')

        s3.download_file(bucket, remote_filename, local_filename)


class SESHelper(BaseLogger):
    """
    SES Helper class.
    """

    def send_raw_email(self, sender, recipient, rawmessage, region=None):
        self.logger.debug('Sending a message from: {0}, to: {1}, \nMessage: {2}'.format(
            sender, str(recipient), rawmessage.as_string()))

        if region:
            ses = boto3.client('ses', region_name=region)
        else:
            ses = boto3.client('ses', region_name='us-east-1')

        result = ses.send_raw_email(
            Source=sender,
            Destinations=recipient.split(','),
            RawMessage={'Data': rawmessage.as_string()}
        )

        return result


def load_config(default_path='config.yaml', default_bucket='aurora-version-checking',
                config_bucket=CONFIG_BUCKET, config_path=CONFIG_FILE):
    """
    Load config
    """

    # Use default or given bucket and config file names
    path = default_path
    if config_path:
        path = config_path
    bucket = default_bucket
    if config_bucket:
        bucket = config_bucket

    # Retrieve config yaml file from bucket and filename specified in the respective env variable.
    s3_helper = S3Helper()
    try:
        s3_helper.download_file(bucket, path, '/tmp/' + path, enable_logging=False)
    # except botocore.exceptions.ClientError as e:
    #     if e.response['Error']['Code'] == "404":
    #         # If this is the first invocation, upload the default config yaml file to S3
    #         s3_helper.upload_file(bucket, path, path, enable_logging=False)
    except:
        copyfile(path, '/tmp/' + path)

    try:
        with open('/tmp/' + path, 'r') as f:
            log_config = yaml.safe_load(f.read())
    except FileNotFoundError as e:
        with open('/tmp/' + path, 'r') as f:
            log_config = yaml.safe_load(f.read())

    s3_helper.upload_file(bucket, path, path, enable_logging=False)

    return log_config


def setup_logging(log_config, default_level=logging.INFO):
    """
    Setup logging configuration
    """

    global config
    path = 'log_config.yaml'  # Default file if no log config file path is given
    if log_config:
        path = log_config
    if os.path.exists(path):
        with open(path, 'r') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


load_config()
setup_logging(log_config=load_config()['log_config'])
