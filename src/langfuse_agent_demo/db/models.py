"""SQLAlchemy ORM models for the Northwind SQLite database (``data/northwind.db``).

Python attributes use snake_case; the original PascalCase column and table names are
kept as the database identifiers. Views in the database are not mapped.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Dialect,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    Table,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Money = Numeric(10, 2)


class TextBoolean(TypeDecorator[bool]):
    """Boolean stored as the TEXT values ``'0'`` / ``'1'`` (e.g. ``Products.Discontinued``)."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: bool | None, dialect: Dialect) -> str | None:
        return None if value is None else ("1" if value else "0")

    def process_result_value(self, value: str | None, dialect: Dialect) -> bool | None:
        return None if value is None else value not in ("0", "")


class Base(DeclarativeBase):
    pass


customer_customer_demo = Table(
    "CustomerCustomerDemo",
    Base.metadata,
    Column("CustomerID", Text, ForeignKey("Customers.CustomerID"), primary_key=True),
    Column(
        "CustomerTypeID",
        Text,
        ForeignKey("CustomerDemographics.CustomerTypeID"),
        primary_key=True,
    ),
)

employee_territories = Table(
    "EmployeeTerritories",
    Base.metadata,
    Column("EmployeeID", ForeignKey("Employees.EmployeeID"), primary_key=True),
    Column("TerritoryID", Text, ForeignKey("Territories.TerritoryID"), primary_key=True),
)


class Category(Base):
    __tablename__ = "Categories"

    category_id: Mapped[int] = mapped_column("CategoryID", primary_key=True)
    category_name: Mapped[str | None] = mapped_column("CategoryName", Text)
    description: Mapped[str | None] = mapped_column("Description", Text)
    picture: Mapped[bytes | None] = mapped_column("Picture", LargeBinary, deferred=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class CustomerDemographic(Base):
    __tablename__ = "CustomerDemographics"

    customer_type_id: Mapped[str] = mapped_column("CustomerTypeID", Text, primary_key=True)
    customer_desc: Mapped[str | None] = mapped_column("CustomerDesc", Text)

    customers: Mapped[list["Customer"]] = relationship(
        secondary=customer_customer_demo, back_populates="demographics"
    )


class Customer(Base):
    __tablename__ = "Customers"

    customer_id: Mapped[str] = mapped_column("CustomerID", Text, primary_key=True)
    company_name: Mapped[str | None] = mapped_column("CompanyName", Text)
    contact_name: Mapped[str | None] = mapped_column("ContactName", Text)
    contact_title: Mapped[str | None] = mapped_column("ContactTitle", Text)
    address: Mapped[str | None] = mapped_column("Address", Text)
    city: Mapped[str | None] = mapped_column("City", Text)
    region: Mapped[str | None] = mapped_column("Region", Text)
    postal_code: Mapped[str | None] = mapped_column("PostalCode", Text)
    country: Mapped[str | None] = mapped_column("Country", Text)
    phone: Mapped[str | None] = mapped_column("Phone", Text)
    fax: Mapped[str | None] = mapped_column("Fax", Text)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    demographics: Mapped[list[CustomerDemographic]] = relationship(
        secondary=customer_customer_demo, back_populates="customers"
    )


class Employee(Base):
    __tablename__ = "Employees"

    employee_id: Mapped[int] = mapped_column("EmployeeID", primary_key=True)
    last_name: Mapped[str | None] = mapped_column("LastName", Text)
    first_name: Mapped[str | None] = mapped_column("FirstName", Text)
    title: Mapped[str | None] = mapped_column("Title", Text)
    title_of_courtesy: Mapped[str | None] = mapped_column("TitleOfCourtesy", Text)
    birth_date: Mapped[date | None] = mapped_column("BirthDate", Date)
    hire_date: Mapped[date | None] = mapped_column("HireDate", Date)
    address: Mapped[str | None] = mapped_column("Address", Text)
    city: Mapped[str | None] = mapped_column("City", Text)
    region: Mapped[str | None] = mapped_column("Region", Text)
    postal_code: Mapped[str | None] = mapped_column("PostalCode", Text)
    country: Mapped[str | None] = mapped_column("Country", Text)
    home_phone: Mapped[str | None] = mapped_column("HomePhone", Text)
    extension: Mapped[str | None] = mapped_column("Extension", Text)
    photo: Mapped[bytes | None] = mapped_column("Photo", LargeBinary, deferred=True)
    notes: Mapped[str | None] = mapped_column("Notes", Text)
    reports_to: Mapped[int | None] = mapped_column("ReportsTo", ForeignKey("Employees.EmployeeID"))
    photo_path: Mapped[str | None] = mapped_column("PhotoPath", Text)

    manager: Mapped["Employee | None"] = relationship(
        remote_side=[employee_id], back_populates="direct_reports"
    )
    direct_reports: Mapped[list["Employee"]] = relationship(back_populates="manager")
    orders: Mapped[list["Order"]] = relationship(back_populates="employee")
    territories: Mapped[list["Territory"]] = relationship(
        secondary=employee_territories, back_populates="employees"
    )


class Region(Base):
    __tablename__ = "Regions"

    region_id: Mapped[int] = mapped_column("RegionID", primary_key=True, autoincrement=False)
    region_description: Mapped[str] = mapped_column("RegionDescription", Text)

    territories: Mapped[list["Territory"]] = relationship(back_populates="region")


class Territory(Base):
    __tablename__ = "Territories"

    territory_id: Mapped[str] = mapped_column("TerritoryID", Text, primary_key=True)
    territory_description: Mapped[str] = mapped_column("TerritoryDescription", Text)
    region_id: Mapped[int] = mapped_column("RegionID", ForeignKey("Regions.RegionID"))

    region: Mapped[Region] = relationship(back_populates="territories")
    employees: Mapped[list[Employee]] = relationship(
        secondary=employee_territories, back_populates="territories"
    )


class Shipper(Base):
    __tablename__ = "Shippers"

    shipper_id: Mapped[int] = mapped_column("ShipperID", primary_key=True)
    company_name: Mapped[str] = mapped_column("CompanyName", Text)
    phone: Mapped[str | None] = mapped_column("Phone", Text)

    orders: Mapped[list["Order"]] = relationship(back_populates="shipper")


class Supplier(Base):
    __tablename__ = "Suppliers"

    supplier_id: Mapped[int] = mapped_column("SupplierID", primary_key=True)
    company_name: Mapped[str] = mapped_column("CompanyName", Text)
    contact_name: Mapped[str | None] = mapped_column("ContactName", Text)
    contact_title: Mapped[str | None] = mapped_column("ContactTitle", Text)
    address: Mapped[str | None] = mapped_column("Address", Text)
    city: Mapped[str | None] = mapped_column("City", Text)
    region: Mapped[str | None] = mapped_column("Region", Text)
    postal_code: Mapped[str | None] = mapped_column("PostalCode", Text)
    country: Mapped[str | None] = mapped_column("Country", Text)
    phone: Mapped[str | None] = mapped_column("Phone", Text)
    fax: Mapped[str | None] = mapped_column("Fax", Text)
    home_page: Mapped[str | None] = mapped_column("HomePage", Text)

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "Products"

    product_id: Mapped[int] = mapped_column("ProductID", primary_key=True)
    product_name: Mapped[str] = mapped_column("ProductName", Text)
    supplier_id: Mapped[int | None] = mapped_column(
        "SupplierID", ForeignKey("Suppliers.SupplierID")
    )
    category_id: Mapped[int | None] = mapped_column(
        "CategoryID", ForeignKey("Categories.CategoryID")
    )
    quantity_per_unit: Mapped[str | None] = mapped_column("QuantityPerUnit", Text)
    unit_price: Mapped[Decimal | None] = mapped_column("UnitPrice", Money, default=0)
    units_in_stock: Mapped[int | None] = mapped_column("UnitsInStock", default=0)
    units_on_order: Mapped[int | None] = mapped_column("UnitsOnOrder", default=0)
    reorder_level: Mapped[int | None] = mapped_column("ReorderLevel", default=0)
    discontinued: Mapped[bool] = mapped_column("Discontinued", TextBoolean, default=False)

    supplier: Mapped[Supplier | None] = relationship(back_populates="products")
    category: Mapped[Category | None] = relationship(back_populates="products")
    order_details: Mapped[list["OrderDetail"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "Orders"

    order_id: Mapped[int] = mapped_column("OrderID", primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(
        "CustomerID", Text, ForeignKey("Customers.CustomerID")
    )
    employee_id: Mapped[int | None] = mapped_column(
        "EmployeeID", ForeignKey("Employees.EmployeeID")
    )
    # Stored as either 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'; both parse to datetime.
    order_date: Mapped[datetime | None] = mapped_column("OrderDate", DateTime)
    required_date: Mapped[datetime | None] = mapped_column("RequiredDate", DateTime)
    shipped_date: Mapped[datetime | None] = mapped_column("ShippedDate", DateTime)
    ship_via: Mapped[int | None] = mapped_column("ShipVia", ForeignKey("Shippers.ShipperID"))
    freight: Mapped[Decimal | None] = mapped_column("Freight", Money, default=0)
    ship_name: Mapped[str | None] = mapped_column("ShipName", Text)
    ship_address: Mapped[str | None] = mapped_column("ShipAddress", Text)
    ship_city: Mapped[str | None] = mapped_column("ShipCity", Text)
    ship_region: Mapped[str | None] = mapped_column("ShipRegion", Text)
    ship_postal_code: Mapped[str | None] = mapped_column("ShipPostalCode", Text)
    ship_country: Mapped[str | None] = mapped_column("ShipCountry", Text)

    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    employee: Mapped[Employee | None] = relationship(back_populates="orders")
    shipper: Mapped[Shipper | None] = relationship(back_populates="orders")
    order_details: Mapped[list["OrderDetail"]] = relationship(back_populates="order")


class OrderDetail(Base):
    __tablename__ = "Order Details"

    order_id: Mapped[int] = mapped_column("OrderID", ForeignKey("Orders.OrderID"), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        "ProductID", ForeignKey("Products.ProductID"), primary_key=True
    )
    unit_price: Mapped[Decimal] = mapped_column("UnitPrice", Money, default=0)
    quantity: Mapped[int] = mapped_column("Quantity", default=1)
    discount: Mapped[float] = mapped_column("Discount", default=0.0)

    order: Mapped[Order] = relationship(back_populates="order_details")
    product: Mapped[Product] = relationship(back_populates="order_details")
