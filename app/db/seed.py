# app/db/seed.py
# Idempotent seed data: a starter set of industries/standards/templates so
# the platform isn't empty on first load. Run with: python -m app.db.seed

import asyncio
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Industry, Standard, AssessmentTemplate

SEED = {
    "Healthcare": {
        "slug": "healthcare",
        "description": "Hospitals, clinics, health tech, and health insurers.",
        "standards": {
            "HIPAA": ("Health data privacy and security compliance.", ["HIPAA Compliance Assessment"]),
            "HITRUST": ("Common security framework for healthcare organizations.", ["HITRUST Readiness Assessment"]),
            "FDA Compliance": ("Regulatory compliance for medical devices/software.", ["FDA Software Compliance Assessment"]),
            "ISO 27001": ("Information security management for health data.", ["ISO 27001 Maturity Assessment"]),
        },
    },
    "Financial Services": {
        "slug": "financial-services",
        "description": "Banks, fintechs, payment processors, and insurers.",
        "standards": {
            "PCI DSS": ("Payment card data security standard.", ["PCI DSS Readiness Assessment"]),
            "SOX": ("Sarbanes-Oxley financial controls compliance.", ["SOX Controls Maturity Assessment"]),
            "FINRA": ("Broker-dealer regulatory compliance.", ["FINRA Compliance Assessment"]),
            "ISO Standards": ("General ISO management-system alignment.", ["ISO Readiness Assessment"]),
        },
    },
    "Manufacturing": {
        "slug": "manufacturing",
        "description": "Industrial, consumer goods, and process manufacturing.",
        "standards": {
            "ISO 9001": ("Quality management systems.", ["ISO 9001 Quality Maturity Assessment"]),
            "ISO 14001": ("Environmental management systems.", ["ISO 14001 Readiness Assessment"]),
            "CMMI": ("Process capability maturity.", ["CMMI Process Maturity Assessment"]),
            "OSHA": ("Workplace safety compliance.", ["OSHA Safety Compliance Assessment"]),
        },
    },
    "Software & Technology": {
        "slug": "software-technology",
        "description": "Software product companies and technology service providers.",
        "standards": {
            "SOC 2": ("Trust-services criteria for SaaS providers.", ["SOC 2 Readiness Assessment"]),
            "ISO 27001": ("Information security management system.", ["ISO 27001 Maturity Assessment"]),
            "GDPR": ("EU data protection and privacy compliance.", ["GDPR Compliance Assessment"]),
            "CMMI": ("Software process capability maturity.", ["CMMI Maturity Assessment"]),
        },
    },
    "Government": {
        "slug": "government",
        "description": "Public sector agencies and government contractors.",
        "standards": {
            "NIST 800-53": ("Federal information security controls.", ["NIST 800-53 Readiness Assessment"]),
            "FedRAMP": ("Cloud security authorization for federal agencies.", ["FedRAMP Readiness Assessment"]),
            "CMMI": ("Process capability maturity for public-sector delivery.", ["CMMI Process Maturity Assessment"]),
        },
    },
    "Retail": {
        "slug": "retail",
        "description": "Retailers, e-commerce, and consumer brands.",
        "standards": {
            "PCI DSS": ("Payment card data security standard.", ["PCI DSS Readiness Assessment"]),
            "ISO 9001": ("Quality management for retail operations.", ["ISO 9001 Quality Maturity Assessment"]),
        },
    },
    "Education": {
        "slug": "education",
        "description": "Universities, K-12 systems, and edtech providers.",
        "standards": {
            "FERPA": ("Student education-record privacy compliance.", ["FERPA Compliance Assessment"]),
            "ISO 27001": ("Information security management for student data.", ["ISO 27001 Maturity Assessment"]),
        },
    },
    "Energy": {
        "slug": "energy",
        "description": "Utilities, oil & gas, and renewable energy operators.",
        "standards": {
            "NERC CIP": ("Critical infrastructure protection standards.", ["NERC CIP Readiness Assessment"]),
            "ISO 14001": ("Environmental management systems.", ["ISO 14001 Readiness Assessment"]),
        },
    },
}


async def seed():
    async with SessionLocal() as db:
        for industry_name, industry_data in SEED.items():
            result = await db.execute(select(Industry).where(Industry.slug == industry_data["slug"]))
            industry = result.scalar_one_or_none()
            if not industry:
                industry = Industry(name=industry_name, slug=industry_data["slug"], description=industry_data["description"])
                db.add(industry)
                await db.flush()
                print(f"+ industry: {industry_name}")

            for standard_name, (description, template_names) in industry_data["standards"].items():
                slug = f"{industry_data['slug']}-{standard_name.lower().replace(' ', '-')}"
                result = await db.execute(select(Standard).where(Standard.slug == slug))
                standard = result.scalar_one_or_none()
                if not standard:
                    standard = Standard(industry_id=industry.id, name=standard_name, slug=slug, description=description)
                    db.add(standard)
                    await db.flush()
                    print(f"  + standard: {standard_name}")

                for template_name in template_names:
                    result = await db.execute(
                        select(AssessmentTemplate).where(
                            AssessmentTemplate.standard_id == standard.id,
                            AssessmentTemplate.name == template_name,
                        )
                    )
                    if not result.scalar_one_or_none():
                        db.add(AssessmentTemplate(
                            standard_id=standard.id, name=template_name,
                            description=f"AI-generated {template_name.lower()} against {standard_name}.",
                        ))
                        print(f"    + template: {template_name}")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
