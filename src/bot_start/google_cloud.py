# coding=UTF-8

import logging
import os

logger = logging.getLogger(__name__)


# noinspection PyPackageRequirements
def auth_google_vision(account_file):
    from google.oauth2 import service_account
    from google.cloud import vision
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        credentials = service_account.Credentials.from_service_account_file(
            current_dir + '/../../' + account_file)
        scoped_credentials = credentials.with_scopes(
            ['https://www.googleapis.com/auth/cloud-platform'])
        return vision.ImageAnnotatorClient(credentials=scoped_credentials)
    except Exception as ex:
        logger.error(ex)
        return None
