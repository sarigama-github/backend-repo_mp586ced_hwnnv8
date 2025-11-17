import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Plant, User, FarmerProfile, MilkCollection, QualityTest, Duty

app = FastAPI(title="India Agro Tech API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class ObjId(BaseModel):
    id: str

def to_object_id(id_str: str):
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def collection_name(model_cls) -> str:
    return model_cls.__name__.lower()


@app.get("/")
def root():
    return {"brand": "India Agro Tech", "message": "Milk plant backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# ------- Auth-lite (role in header) -------
ROLE_HEADER = "x-role"
PLANT_HEADER = "x-plant-id"
USER_HEADER = "x-user-id"

class RoleContext(BaseModel):
    role: str
    plant_id: Optional[str] = None
    user_id: Optional[str] = None


def get_role_ctx(role: Optional[str] = None, plant_id: Optional[str] = None, user_id: Optional[str] = None):
    # In real app use auth. Here, read from headers via dependency.
    return RoleContext(role=role, plant_id=plant_id, user_id=user_id)


# ------------ Admin/Super Admin: Plants ------------
@app.post("/plants", response_model=dict)
def create_plant(plant: Plant, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admin can create plants")
    plant_id = create_document(collection_name(Plant), plant)
    return {"id": plant_id}


@app.get("/plants", response_model=List[dict])
def list_plants(ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return get_documents(collection_name(Plant))


# ------------ Users ------------
@app.post("/users", response_model=dict)
def create_user(user: User, ctx: RoleContext = Depends(get_role_ctx)):
    # super_admin can create any user, admin can create farmer/feeder/tester within their plant
    if ctx.role == "super_admin":
        pass
    elif ctx.role == "admin":
        if user.role not in ["farmer", "feeder", "tester"]:
            raise HTTPException(status_code=403, detail="Admin can only create farmer/feeder/tester")
        # force plant id to admin's plant
        if ctx.plant_id:
            user.plant_id = ctx.plant_id
        else:
            raise HTTPException(status_code=400, detail="Admin must be scoped to a plant")
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")
    new_id = create_document(collection_name(User), user)
    return {"id": new_id}


@app.get("/users", response_model=List[dict])
def list_users(role: Optional[str] = None, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    filt = {}
    if role:
        filt["role"] = role
    if ctx.role == "admin" and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    return get_documents(collection_name(User), filt)


# ------------ Farmer Profile ------------
@app.post("/farmer-profiles", response_model=dict)
def create_farmer_profile(profile: FarmerProfile, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin/super admin can create profiles")
    new_id = create_document(collection_name(FarmerProfile), profile)
    return {"id": new_id}


@app.get("/farmer-profiles", response_model=List[dict])
def list_farmer_profiles(ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    filt = {}
    if ctx.role == "admin" and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    return get_documents(collection_name(FarmerProfile), filt)


# ------------ Milk Collection (Feeder) ------------
@app.post("/collections", response_model=dict)
def add_collection(entry: MilkCollection, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["feeder", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only feeder/admin/super can record collections")
    # admin limited to their plant
    if ctx.role == "admin" and ctx.plant_id and entry.plant_id != ctx.plant_id:
        raise HTTPException(status_code=403, detail="Admin can only record within assigned plant")
    new_id = create_document(collection_name(MilkCollection), entry)
    return {"id": new_id}


@app.get("/collections", response_model=List[dict])
def list_collections(plant_id: Optional[str] = None, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["feeder", "tester", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    filt = {}
    if plant_id:
        filt["plant_id"] = plant_id
    if ctx.role == "admin" and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    if ctx.role in ["feeder", "tester"] and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    return get_documents(collection_name(MilkCollection), filt)


# ------------ Quality Tests (Tester) ------------
@app.post("/quality-tests", response_model=dict)
def add_quality_test(test: QualityTest, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["tester", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only tester/admin/super can record tests")
    if ctx.role == "admin" and ctx.plant_id and test.plant_id != ctx.plant_id:
        raise HTTPException(status_code=403, detail="Admin can only record within assigned plant")
    new_id = create_document(collection_name(QualityTest), test)
    return {"id": new_id}


@app.get("/quality-tests", response_model=List[dict])
def list_quality_tests(plant_id: Optional[str] = None, ctx: RoleContext = Depends(get_role_ctx)):
    if ctx.role not in ["tester", "admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    filt = {}
    if plant_id:
        filt["plant_id"] = plant_id
    if ctx.role == "admin" and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    if ctx.role == "tester" and ctx.plant_id:
        filt["plant_id"] = ctx.plant_id
    return get_documents(collection_name(QualityTest), filt)


# ------------ Duties (static reference per role) ------------
DEFAULT_DUTIES = [
    {"role": "super_admin", "title": "Manage all plants", "description": "Full visibility and control across the system"},
    {"role": "admin", "title": "Manage assigned plant", "description": "Manage users, collections, tests for their plant"},
    {"role": "farmer", "title": "View deliveries", "description": "Track your milk deliveries and payments"},
    {"role": "feeder", "title": "Record milk collection", "description": "Collect milk from farmers and record quantities"},
    {"role": "tester", "title": "Record quality tests", "description": "Perform fat/SNF testing for batches"},
]

@app.get("/duties", response_model=List[Duty])
def get_duties(role: Optional[str] = None):
    duties = [Duty(**d) for d in DEFAULT_DUTIES]
    if role:
        duties = [d for d in duties if d.role == role]
    return duties


# --------- Public schema for viewer (optional) ---------
@app.get("/schema")
def get_schema():
    return {
        "collections": [
            "plant",
            "user",
            "farmerprofile",
            "milkcollection",
            "qualitytest",
            "duty",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
