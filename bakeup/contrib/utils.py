import json
import re

from django.http import HttpResponse
from django.utils.html import strip_tags


def get_json_http_response(message, success=True, errors=None, status=200):
    """Returns an HTTP Response with a valid JSON formatted body.
    :param message: Message to convey in the response
    :type message: str
    :param success: `True` to convey success, `False` otherwise, defaults to `True`
    :type success: bool, optional
    :param errors: Dictionary of errors, defaults to None
    :type errors: dict, optional
    :param status: HTTP Status Code, defaults to 200
    :type status: int, optional
    :return: HTTP Response with JSON body
    :rtype: class:`django.http.HttpResponse`
    """
    return HttpResponse(
        content=json.dumps(
            {
                "success": success,
                "message": message,
                "errors": errors,
            }
        ),
        status=status,
    )


def html_to_plaintext(html):
    """
    Converts `html` to plaintext.
    :param html: HTML formatted string
    :type html: str
    :return: Plaintext representation of the HTML input
    :rtype: str
    """
    plaintext = re.sub(
        "[ \t]+", " ", strip_tags(html)
    )  # Remove html tags and continuous whitespaces
    plaintext = plaintext.replace(
        "\n ", "\n"
    ).strip()  # Strip single spaces in the beginning of each line
    return plaintext
