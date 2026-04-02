"""Generate mock policy PDF documents for the RAG pipeline."""
from fpdf import FPDF
import os

POLICIES_DIR = os.path.join(os.path.dirname(__file__), "policies")


def create_policy_pdf(filename: str, title: str, sections: list[dict]):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    for section in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, section["heading"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, section["body"])
        pdf.ln(3)

    pdf.output(os.path.join(POLICIES_DIR, filename))


BASIC_SECTIONS = [
    {"heading": "Section 1 - Policy Overview",
     "body": "This Basic Roadside Assistance Policy provides essential coverage for vehicle breakdowns and emergencies. Coverage is limited to the policyholder's registered vehicle only. This policy does not cover rental vehicles, borrowed vehicles, or vehicles not listed on the policy."},
    {"heading": "Section 2 - Towing Services",
     "body": "Towing is covered up to 25 miles from the point of breakdown to the nearest approved repair facility. Towing beyond 25 miles will incur additional charges at the policyholder's expense. Maximum of 2 tow claims per policy year. Towing must be performed by an approved service provider."},
    {"heading": "Section 3 - Flat Tire Assistance",
     "body": "Flat tire change service is covered when a serviceable spare tire is available in the vehicle. If no spare is available, towing to the nearest tire shop is covered under Section 2 limits. This service covers labor only; the cost of a new tire is the policyholder's responsibility."},
    {"heading": "Section 4 - Fuel Delivery",
     "body": "Emergency fuel delivery of up to 2 gallons is covered when the vehicle runs out of fuel. The cost of fuel is the policyholder's responsibility. This service is limited to 1 occurrence per policy year. Diesel fuel delivery is not covered under the Basic plan."},
    {"heading": "Section 5 - Lockout Service",
     "body": "Lockout service is NOT covered under the Basic plan. Policyholders requiring lockout assistance should contact a local locksmith at their own expense. Upgrade to Standard or Premium plan for lockout coverage."},
    {"heading": "Section 6 - Exclusions",
     "body": "The following are excluded from coverage: (a) Accidents requiring emergency medical response - call 911. (b) Vehicle recovery from off-road locations, ditches, or water. (c) Breakdowns due to pre-existing mechanical conditions known at policy inception. (d) Commercial vehicles or vehicles used for ride-sharing services. (e) Incidents occurring outside the continental United States."},
    {"heading": "Section 7 - Claims Process",
     "body": "To file a claim, contact our 24/7 roadside assistance hotline. Provide your policy number, vehicle information, location, and description of the incident. A service provider will be dispatched within the estimated arrival time. All claims are subject to verification and policy limits."},
]

STANDARD_SECTIONS = [
    {"heading": "Section 1 - Policy Overview",
     "body": "This Standard Roadside Assistance Policy provides comprehensive coverage for vehicle breakdowns and road emergencies. Coverage extends to the policyholder's registered vehicle and one additional vehicle registered to a household member. Coverage applies 24 hours a day, 365 days a year within the continental United States."},
    {"heading": "Section 2 - Towing Services",
     "body": "Towing is covered up to 50 miles from the point of breakdown to a repair facility of the policyholder's choice. Towing beyond 50 miles will incur charges at $3 per additional mile. Maximum of 4 tow claims per policy year. Both flatbed and wheel-lift towing methods are covered."},
    {"heading": "Section 3 - Flat Tire Assistance",
     "body": "Flat tire change service is fully covered including labor and basic tire mounting. If the vehicle does not have a usable spare tire, towing to the nearest tire shop is covered under Section 2. Run-flat tire service is also covered."},
    {"heading": "Section 4 - Fuel Delivery",
     "body": "Emergency fuel delivery of up to 3 gallons is covered, including the cost of regular unleaded fuel. Premium fuel and diesel delivery are covered but fuel cost above regular unleaded price is the policyholder's responsibility. Limited to 2 occurrences per policy year."},
    {"heading": "Section 5 - Lockout Service",
     "body": "Lockout service is covered up to 2 occurrences per policy year. This includes standard key-in-car lockout assistance. If the vehicle requires specialized locksmith tools (e.g., transponder key programming), additional costs beyond $75 are the policyholder's responsibility. Key replacement is not covered."},
    {"heading": "Section 6 - Battery Jump Start",
     "body": "Battery jump-start service is covered with no per-incident limit. If the battery cannot be jump-started, towing to the nearest repair facility is covered under Section 2. Battery replacement is not covered under this service."},
    {"heading": "Section 7 - Minor Accident Assistance",
     "body": "For minor accidents (no injuries, vehicles are drivable), the Standard plan covers coordination of towing if needed and provides a detailed incident report for insurance claims. This does NOT constitute accident insurance coverage. For accidents involving injuries, call 911 immediately."},
    {"heading": "Section 8 - Exclusions",
     "body": "The following are excluded from coverage: (a) Vehicle recovery from off-road locations or bodies of water. (b) Breakdowns of commercial vehicles or vehicles used for ride-sharing. (c) Pre-existing mechanical failures documented prior to policy start. (d) Cosmetic damage or non-mechanical issues. (e) Incidents outside the continental United States."},
]

PREMIUM_SECTIONS = [
    {"heading": "Section 1 - Policy Overview",
     "body": "This Premium Roadside Assistance Policy provides the highest level of coverage for all vehicle emergencies. Coverage extends to all vehicles owned or regularly operated by the policyholder and immediate family members. Coverage applies worldwide where our service network operates, including Canada and Mexico."},
    {"heading": "Section 2 - Towing Services",
     "body": "Unlimited distance towing is covered to any repair facility of the policyholder's choice. No per-incident or annual claim limits apply. All towing methods are covered including flatbed, wheel-lift, and motorcycle towing. Storage fees at the destination facility are covered for up to 72 hours."},
    {"heading": "Section 3 - Flat Tire Assistance",
     "body": "Full flat tire service is covered including tire change, tire repair (plug or patch), and emergency tire replacement up to $150 per tire. If no spare is available, mobile tire service or towing is covered at no additional cost. Run-flat and specialty tire service included."},
    {"heading": "Section 4 - Fuel Delivery",
     "body": "Emergency fuel delivery of up to 5 gallons is fully covered including the cost of fuel (all grades including premium and diesel). Electric vehicle charge assistance is also covered - a mobile charging unit will provide sufficient charge to reach the nearest charging station. Unlimited occurrences per policy year."},
    {"heading": "Section 5 - Lockout Service",
     "body": "Comprehensive lockout service is covered with unlimited occurrences. This includes standard lockout, transponder key programming (up to $200), emergency key cutting, and smart key battery replacement. Replacement key costs are covered up to $300 per occurrence."},
    {"heading": "Section 6 - Battery Service",
     "body": "Battery jump-start service is covered with no limits. If the battery cannot be jump-started, on-site battery replacement is covered up to $200 for the battery cost plus labor. Battery testing and diagnostic service is included at no charge."},
    {"heading": "Section 7 - Accident Assistance",
     "body": "For all accidents, the Premium plan provides: (a) Priority towing dispatch with average 20-minute response time. (b) Coordination with emergency services if needed. (c) Rental car arrangement (rental cost not covered). (d) Detailed incident documentation and photography. (e) Direct communication with your insurance claims adjuster. This does NOT constitute accident insurance coverage."},
    {"heading": "Section 8 - Vehicle Recovery",
     "body": "Unlike Basic and Standard plans, the Premium plan covers vehicle recovery from off-road locations, ditches, snow banks, and mud. Winching service up to 100 feet is covered. Recovery from bodies of water is covered up to $1,000 in service costs."},
    {"heading": "Section 9 - Trip Interruption Benefits",
     "body": "If a breakdown occurs more than 100 miles from home and the vehicle cannot be repaired same-day, the Premium plan covers: hotel accommodation up to $150/night for up to 3 nights, meal expenses up to $75/day, and alternative transportation up to $200. Receipts required for reimbursement."},
    {"heading": "Section 10 - Exclusions",
     "body": "The following are excluded from coverage: (a) Pre-existing mechanical failures documented prior to policy start. (b) Intentional damage to the vehicle. (c) Racing, competition, or off-road recreational use. (d) Vehicles exceeding 10,000 lbs gross weight. (e) Acts of war or terrorism."},
]


if __name__ == "__main__":
    os.makedirs(POLICIES_DIR, exist_ok=True)
    create_policy_pdf("basic_roadside_policy.pdf", "Basic Roadside Assistance Policy", BASIC_SECTIONS)
    create_policy_pdf("standard_roadside_policy.pdf", "Standard Roadside Assistance Policy", STANDARD_SECTIONS)
    create_policy_pdf("premium_roadside_policy.pdf", "Premium Roadside Assistance Policy", PREMIUM_SECTIONS)
    print("Generated 3 policy PDFs in", POLICIES_DIR)
