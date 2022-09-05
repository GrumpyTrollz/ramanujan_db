import logging
import config
from sqlalchemy.orm import sessionmaker
from . import models
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

class RamanujanDB(object):
    def __init__(self):
        logging.debug("Trying to connect to database")
        self._engine = create_engine(config.get_connection_string(), echo=False)
        Session = sessionmaker(bind=self._engine)
        self.session = Session()
        logging.debug("Connected to database")

    @property
    def constants(self):
        return self.session.query(models.Constant).order_by(models.Constant.constant_id)

    @property
    def cfs(self):
        return self.session.query(models.Cf).order_by(models.Cf.cf_id)

    def add_cfs(self, cf_list, conflict=False):
        if not conflict:
            self.session.add_all(cf_list)
            self.session.commit()
        else:
            insert_statement = postgresql.insert(models.Cf).values(cf_list)
            self._engine.execute(insert_statement.on_conflict_do_nothing())


