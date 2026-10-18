import configparser
import os

_tr = configparser.ConfigParser()
_INI = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    'interface', 'en.ini')
_tr.read(_INI, encoding='utf-8')

tr = _tr
