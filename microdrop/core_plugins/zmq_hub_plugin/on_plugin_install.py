from datetime import datetime
import logging

from path_helpers import path
from pip_helpers import install


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.info(str(datetime.now()))
    requirements_file = path(__file__).parent.joinpath('requirements.txt')
    if requirements_file.exists():
        logging.info(install(['-r', requirements_file]))
