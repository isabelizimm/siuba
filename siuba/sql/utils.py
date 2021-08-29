import importlib

def get_dialect_funcs(name):
    #dialect = engine.dialect.name
    mod = importlib.import_module('siuba.sql.dialects.{}'.format(name))
    return mod.funcs

def get_sql_classes(name):
    mod = importlib.import_module('siuba.sql.dialects.{}'.format(name))
    win_name = name.title() + "Column"
    agg_name = name.title() + "ColumnAgg"
    return {
            'window': getattr(mod, win_name),
            'aggregate': getattr(mod, agg_name)
            }


def mock_sqlalchemy_engine(dialect):
    """
    Create a sqlalchemy.engine.Engine without it connecting to a database.

    Examples
    --------

    ::
        from siuba.sql import LazyTbl
        from siuba import _, mutate, show_query

        engine = mock_sqlalchemy_engine('postgresql')
        tbl = LazyTbl(engine, 'some_table', ['x'])

        query = mutate(tbl, y = _.x + _.x)
        show_query(query)

    """
    from sqlalchemy.engine import Engine
    from sqlalchemy.dialects import registry

    dialect_cls = registry.load('postgresql')   
    return Engine(None, dialect_cls(), '')  


# Temporary fix for pandas bug (https://github.com/pandas-dev/pandas/issues/35484)
from pandas.io import sql as _pd_sql

class _FixedSqlDatabase(_pd_sql.SQLDatabase):
    def execute(self, *args, **kwargs):
        return self.connectable.execute(*args, **kwargs)


# Backwards compatibility for sqlalchemy 1.3 ----------------------------------

import re
import sqlalchemy

RE_VERSION=r"(?P<major>\d+)\.(?P<minor>\d+).(?P<patch>\d+)"  
SQLA_VERSION=tuple(map(int, re.match(RE_VERSION, sqlalchemy.__version__).groups()))

def is_sqla_12():
    return SQLA_VERSION[:-1] == (1, 2)

def is_sqla_13():
    return SQLA_VERSION[:-1] == (1, 3)


def _sql_select(columns, *args, **kwargs):
    from sqlalchemy import sql
    if is_sqla_12() or is_sqla_13():
        # use old syntax, where columns are passed as a list
        return sql.select(columns, *args, **kwargs)

    return sql.select(*columns, *args, **kwargs)


def _sql_column_collection(data, columns):
    from sqlalchemy.sql.base import ColumnCollection, ImmutableColumnCollection

    if is_sqla_12() or is_sqla_13():
        return ImmutableColumnCollection(data, columns)

    return ColumnCollection(list(data.items())).as_immutable()


def _sql_add_columns(select, columns):
    if is_sqla_12() or is_sqla_13():
        for column in columns:
            select = select.column(column)
        return select

    return select.add_columns(*columns)


def _sql_refresh(el):
    f_refresh = getattr(
        el,
        "_reset_memoizations",
        getattr(el, "_reset_exported", None)
    )

    f_refresh()


# Simplify option in show_query -----------------------------------------------

def sql_simplify_select(select):
    from sqlalchemy import sql
    from sqlalchemy.sql.visitors import traverse, cloned_traverse

    def simplify_sel(sel):

        if isinstance(sel, sql.Select) and len(sel.froms) == 1:
            child = sel.froms[0]

            # technically should be an ordered set
            crnt_cols = set(sel.inner_columns)
            child_cols = set(child.columns)

            if len(child_cols - crnt_cols) == 0:
                remaining = list(crnt_cols - child_cols)

                star = sql.text("*")
                star._from_objects = (child,)

                sel._raw_columns = [star, *remaining]
                _sql_refresh(sel)

    # TODO: find simpler way to clone an element. We cannot use the visitors
    # argument of cloned_traverse, since it visits the inner-most element first.
    clone_el = cloned_traverse(select, {}, {})

    # modify in-place
    traverse(clone_el, {}, {"select": simplify_sel})

    return clone_el

    


    

