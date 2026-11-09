# Indonesia legal notice — voucher / captive-portal feature

> **Important:** This document is a compliance notice for users in Indonesia. It is not legal advice and it does not create immunity from civil, administrative, contractual, or criminal liability. The firmware is a technical tool only. The person or business operating the hotspot is responsible for ensuring that its use is lawful and permitted by its ISP/operator agreement.

## 1. This firmware does not grant permission to resell Internet access

The voucher feature can technically create time-limited Internet credentials, but the existence of that feature does **not** mean the operator is legally entitled to sell Internet access.

Under Indonesian telecommunications rules, commercial resale of telecommunications services can fall under **Jual Kembali Jasa Telekomunikasi**. Permen Komdigi No. 15 Tahun 2025 expressly includes resale of Internet access, including examples such as Warung Internet / Internet Café, and defines resale as selling telecommunications services through cooperation with a telecommunications service provider.

For a resale arrangement, the regulation requires, among other things:

- a cooperation agreement between the licensed telecommunications service provider and the reseller;
- use of the provider's service trademark, while the reseller may add its own trademark;
- compliance with the service-quality commitments of the provider;
- revenue from the resale activity to be recorded as revenue of the telecommunications service provider;
- billing to display the telecommunications service provider's trademark;
- for IP-based resale, use of the public IP address and Autonomous System Number (ASN) of the telecommunications service provider;
- consumer protection obligations.

Official reference:

- Permen Komdigi No. 15 Tahun 2025, Lampiran I, Standar Kegiatan Usaha Jasa Jual Kembali Jasa Telekomunikasi: https://jdih.komdigi.go.id/produk_hukum/unduh/id/985/t/peraturan%2Bmenteri%2Bkomunikasi%2Bdan%2Bdigital%2Bnomor%2B15%2Btahun%2B2025

## 2. KBLI code: verify the current OSS classification

There is a transition in the public regulatory materials:

- Permen Komdigi No. 15 Tahun 2025 still identifies this activity as **KBLI 61994 — Jasa Jual Kembali Jasa Telekomunikasi**.
- The current OSS KBLI 2025 catalogue lists the equivalent activity as **KBLI 61201 — Aktivitas Penjualan Kembali Jasa Telekomunikasi**.

Because classifications and OSS mappings can change, do **not** rely only on a code copied from this repository. Verify the current code and licensing path in OSS at the time of registration.

Official OSS reference:

- OSS KBLI 2025 — Aktivitas Penjualan Kembali Jasa Telekomunikasi (61201): https://oss.go.id/id/kbli/detail/715fc525-b1cb-557f-a7ac-dcc639aa5f6e

## 3. NIB alone is not a blanket authorization to resell Internet

Having an NIB or selecting a KBLI code does not, by itself, make every resale model lawful. The operator must also satisfy the applicable telecommunications-sector requirements, including the required cooperation arrangement and the obligations imposed on the resale model.

Do not advertise this firmware as making an unlicensed or unauthorized Internet-resale business '100% legal'.

## 4. Residential / consumer ISP plans

Even where a business has general business registration, the underlying ISP or mobile-operator contract may prohibit redistribution, commercial resale, hotspot resale, subletting, or similar use on consumer/residential plans.

Before charging users for Internet access, verify the specific subscription terms and obtain written approval or a proper reseller/business arrangement from the provider where required.

## 5. Complimentary guest Wi-Fi is a different use case, but still requires compliance

A captive portal can also be used to provide **complimentary guest Wi-Fi** as an amenity, for example to customers of a café, hotel, office, event, waiting room, or other venue. A time limit such as one, two, or three hours can be used as an operational policy for bandwidth, security, or guest-session management.

Providing Wi-Fi as a complimentary amenity, without separately selling Internet access, is factually different from charging users for telecommunications access. However, this project does **not** certify that every free-Wi-Fi deployment is automatically lawful in every circumstance. The operator must still comply with:

- the ISP/operator subscription agreement;
- applicable Indonesian telecommunications rules;
- consumer-protection requirements where relevant;
- privacy and personal-data obligations where user information is collected;
- other laws and venue-specific obligations that may apply.

## 6. Recommended lawful-resale path

If the hotspot is intended to charge users for Internet access, the operator should, before launch:

1. Confirm the current business classification and registration requirements in OSS.
2. Use an ISP/operator that explicitly permits resale or offers a reseller/partner programme.
3. Enter into the required written cooperation agreement (PKS) with the telecommunications service provider.
4. Follow the provider-branding, billing, revenue-booking, quality-of-service, IP/ASN, and consumer-protection obligations applicable to the arrangement.
5. Obtain professional legal/compliance advice if the business model is material or unclear.

## 7. Maintainer and user responsibility

This project is open-source firmware and is distributed for lawful network administration, guest-access control, testing, and other legitimate uses.

The maintainers:

- do not sell telecommunications services through this repository;
- do not authorize any user to resell an ISP/operator service;
- do not verify a user's NIB, licence, PKS, ISP contract, tax status, or other legal compliance;
- do not guarantee that a particular deployment is lawful;
- are not responsible for a user's decision to operate the firmware in violation of law, regulation, ISP terms, or third-party rights.

By enabling the voucher/captive-portal feature, the operator accepts responsibility for checking and complying with the rules and contracts that apply to the operator's own deployment.

## 8. Date and change warning

This notice was reviewed against public Indonesian regulatory sources available in **October 2026**. Regulations, KBLI mappings, OSS procedures, and ISP terms can change. Always verify the latest official requirements before commercial deployment.

## Short English notice

The voucher feature is a technical access-control tool and does not grant a right to resell Internet service. Commercial telecommunications resale in Indonesia may be subject to the official resale framework, provider cooperation agreement, branding/billing requirements, consumer-protection duties, and other sector rules. Complimentary guest Wi-Fi is a different use case, but operators must still comply with their ISP contract and applicable law. Verify current OSS/Komdigi requirements before deployment.
