# coding=UTF-8

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from src.config import CONFIG
from src.utils.misc import retry

logger = logging.getLogger(__name__)
Base = declarative_base()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    # session.begin(True)
    try:
        yield session
        session.expunge_all()
        session.commit()
        # session.expire_all()
    except Exception as e:
        session.expunge_all()
        session.rollback()
        # session.expire_all()
        raise
    finally:
        # Session.remove()
        session.close()


@retry(logger=logger)
def add_to_db(value):
    try:
        with session_scope() as db:
            db.add(value)
            db.commit()
    except Exception as e:
        logger.error(e)
        raise Exception("Can't add value to DB")


if 'database' in CONFIG:
    engine = create_engine(CONFIG['database'], convert_unicode=True, echo=False)
    Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
else:
    # print("Can't connect to database")
    pass
