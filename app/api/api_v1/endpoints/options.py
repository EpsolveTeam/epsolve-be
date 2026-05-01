from fastapi import APIRouter

router = APIRouter()

CATEGORIES = [
    "General",
    "Sistem & IT Support",
    "Troubleshooting Perangkat",
    "Service Repair",
    "Maintenance & Setup",
    "Produksi & Operasi",
    "Kebijakan Internal",
    "Penggunaan Tools",
]

DIVISIONS = [
    "Operations",
    "R&D",
    "Marketing",
    "Finance",
    "Customer Service",
]


@router.get("/")
def get_options():
    """
    Mengembalikan data statis untuk dropdown tiket.
    """
    return {
        "categories": CATEGORIES,
        "divisions": DIVISIONS,
    }
