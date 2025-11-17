"""
Database Schemas for India Agro Tech Milk Plant

Each Pydantic model represents a MongoDB collection (collection name is the lowercase of the class name).

Roles:
- super_admin: Full access to everything across plants
- admin: Plant-level management for assigned plant
- farmer: Can view own profile and delivery history
- feeder: Records milk collection from farmers
- tester: Records quality tests for collected milk
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class Plant(BaseModel):
    name: str = Field(..., description="Plant name")
    location: Optional[str] = Field(None, description="Plant location")
    code: Optional[str] = Field(None, description="Unique plant code")


class User(BaseModel):
    full_name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    role: Literal["super_admin", "admin", "farmer", "feeder", "tester"] = Field(..., description="Role of the user")
    plant_id: Optional[str] = Field(None, description="Assigned plant id for non-super roles")
    is_active: bool = Field(True, description="Active status")


class FarmerProfile(BaseModel):
    user_id: str = Field(..., description="Reference to user document")
    farm_name: Optional[str] = None
    village: Optional[str] = None
    milk_animal_count: Optional[int] = Field(default=0, ge=0)


class MilkCollection(BaseModel):
    date: datetime = Field(default_factory=datetime.utcnow)
    plant_id: str = Field(...)
    farmer_id: str = Field(...)
    feeder_id: str = Field(...)
    quantity_liters: float = Field(..., ge=0)
    fat: Optional[float] = Field(None, ge=0, le=100)
    snf: Optional[float] = Field(None, ge=0, le=100)
    shift: Literal["morning", "evening"] = Field(...)


class QualityTest(BaseModel):
    plant_id: str
    collection_id: str
    tester_id: str
    acidity: Optional[float] = Field(None, ge=0, le=100)
    adulteration: Optional[bool] = False
    remarks: Optional[str] = None
    date: datetime = Field(default_factory=datetime.utcnow)


class Duty(BaseModel):
    role: Literal["super_admin", "admin", "farmer", "feeder", "tester"]
    title: str
    description: Optional[str] = None


# Public schema endpoint support (optional helpful for viewers)
class SchemaInfo(BaseModel):
    collections: List[str]
"""
Note: The Flames database viewer may read these via /schema endpoint for inspection.
"""
