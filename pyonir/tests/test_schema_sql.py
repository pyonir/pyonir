from typing import Optional, List
from dataclasses import dataclass

from pyonir.core.schemas import Graphiti

from pyonir import PyonirSchema
from pyonir.tests.conftest import test_pyonir_db, PyonirMockDataBaseService


class MockAccount(PyonirSchema, table_name="mock_account", file_name="person.json"):
    uuid: str
    account_status: str

class MockIdentity(PyonirSchema, table_name="mock_identity", foreign_keys={'account_id'}, unique_keys=['account_id'], file_name="identity.json"):
    account_id: int
    email: str
    password: str

class MockAggrIdentity(MockIdentity, table_name="mock_aggr_identity"):
    email: Optional[str]
    password: Optional[str]

class MockServices:
    @classmethod
    def create_account(cls, email, password) -> tuple[MockAccount, MockIdentity]:
        acct = MockAccount(uuid=f"{email}-123abc", account_status="NEW")
        idty = MockIdentity(account_id=0, email=email, password=password)
        return acct, idty


@dataclass
class Color:
    name: str
    hex: int

@dataclass
class Product:
    price: float | None = None
    weight: float | None = None


@dataclass
class Item:
    title: str | None = None
    url: str | None = None
    product: Product | None = None
    variations: List[Color] | None = None

def test_item():
    item = Item(
        title="Example Item",
        url="https://example.com",
        product=Product(
            price=19.99,
            weight=1.2
        ),
        variations=[Color('red',222), Color('blue', 444), Color('green', 999)]
    )

    schema = "{title,url,product:item{price:cost,weight:wt},variations{name}}"
    mock = Graphiti.parse_query(schema, item)
    print(mock)

def test_sql_create(test_pyonir_db: PyonirMockDataBaseService):
    email, password = "foo@pyonir.com", "123456"
    test_pyonir_db.build_tables_from_models([MockIdentity, MockAccount, MockAggrIdentity])
    acct_a, idty_a = MockServices.create_account("usera@pyonir.com", "333444ddd")
    acct_b, idty_b = MockServices.create_account("userb@pyonir.com", "222eee444")

    # insert first account
    test_pyonir_db.upsert(acct_a)
    idty_a.account_id = acct_a.id
    test_pyonir_db.upsert(idty_a)

    # insert second account
    test_pyonir_db.upsert(acct_b)
    idty_b.account_id = acct_b.id
    rib = test_pyonir_db.upsert(idty_b)

    aggr_idty_b = MockAggrIdentity(account_id=idty_b.account_id, email=email, password=password)
    raib = test_pyonir_db.upsert(aggr_idty_b)

    pass

