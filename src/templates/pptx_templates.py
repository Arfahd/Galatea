"""
PowerPoint presentation templates.
Each template provides a predefined structure with slides in English and Indonesian.
"""

from typing import Optional

# Template definitions
# Each template has:
# - name_en, name_id: Display names
# - description_en, description_id: Short descriptions
# - slides: List of slide definitions with layout, title, subtitle, content

PPTX_TEMPLATES: dict = {
    "blank": {
        "name_en": "Blank Presentation",
        "name_id": "Presentasi Kosong",
        "description_en": "Start with a blank presentation",
        "description_id": "Mulai dengan presentasi kosong",
        "slides": [
            {
                "layout": "title",
                "title_en": "Presentation Title",
                "title_id": "Judul Presentasi",
                "subtitle_en": "Your Name",
                "subtitle_id": "Nama Anda",
            }
        ],
    },
    "business_proposal": {
        "name_en": "Business Proposal",
        "name_id": "Proposal Bisnis",
        "description_en": "Professional business proposal template",
        "description_id": "Template proposal bisnis profesional",
        "slides": [
            {
                "layout": "title",
                "title_en": "Business Proposal",
                "title_id": "Proposal Bisnis",
                "subtitle_en": "Company Name | Date",
                "subtitle_id": "Nama Perusahaan | Tanggal",
            },
            {
                "layout": "content",
                "title_en": "Executive Summary",
                "title_id": "Ringkasan Eksekutif",
                "content_en": "- Brief overview of the proposal\n- Key objectives\n- Expected outcomes",
                "content_id": "- Ringkasan singkat proposal\n- Tujuan utama\n- Hasil yang diharapkan",
            },
            {
                "layout": "content",
                "title_en": "Problem Statement",
                "title_id": "Pernyataan Masalah",
                "content_en": "- Current challenges\n- Impact on business\n- Why action is needed now",
                "content_id": "- Tantangan saat ini\n- Dampak pada bisnis\n- Mengapa perlu tindakan sekarang",
            },
            {
                "layout": "content",
                "title_en": "Proposed Solution",
                "title_id": "Solusi yang Diusulkan",
                "content_en": "- Our approach\n- Key features/benefits\n- Implementation strategy",
                "content_id": "- Pendekatan kami\n- Fitur/manfaat utama\n- Strategi implementasi",
            },
            {
                "layout": "content",
                "title_en": "Timeline",
                "title_id": "Jadwal Waktu",
                "content_en": "- Phase 1: Planning\n- Phase 2: Development\n- Phase 3: Implementation\n- Phase 4: Review",
                "content_id": "- Fase 1: Perencanaan\n- Fase 2: Pengembangan\n- Fase 3: Implementasi\n- Fase 4: Evaluasi",
            },
            {
                "layout": "content",
                "title_en": "Budget Overview",
                "title_id": "Ringkasan Anggaran",
                "content_en": "- Initial investment\n- Operational costs\n- Expected ROI",
                "content_id": "- Investasi awal\n- Biaya operasional\n- ROI yang diharapkan",
            },
            {
                "layout": "content",
                "title_en": "Team",
                "title_id": "Tim",
                "content_en": "- Team Lead\n- Project Manager\n- Technical Team\n- Support Staff",
                "content_id": "- Ketua Tim\n- Manajer Proyek\n- Tim Teknis\n- Staf Pendukung",
            },
            {
                "layout": "content",
                "title_en": "Next Steps",
                "title_id": "Langkah Selanjutnya",
                "content_en": "- Approval process\n- Contract signing\n- Kickoff meeting\n- Project initiation",
                "content_id": "- Proses persetujuan\n- Penandatanganan kontrak\n- Rapat kickoff\n- Inisiasi proyek",
            },
            {
                "layout": "content",
                "title_en": "Questions & Discussion",
                "title_id": "Tanya Jawab & Diskusi",
                "content_en": "Thank you for your attention.\n\nContact: email@company.com",
                "content_id": "Terima kasih atas perhatian Anda.\n\nKontak: email@perusahaan.com",
            },
        ],
    },
    "project_status": {
        "name_en": "Project Status Report",
        "name_id": "Laporan Status Proyek",
        "description_en": "Weekly/monthly project status update",
        "description_id": "Update status proyek mingguan/bulanan",
        "slides": [
            {
                "layout": "title",
                "title_en": "Project Status Report",
                "title_id": "Laporan Status Proyek",
                "subtitle_en": "Project Name | Reporting Period",
                "subtitle_id": "Nama Proyek | Periode Pelaporan",
            },
            {
                "layout": "content",
                "title_en": "Overview",
                "title_id": "Ringkasan",
                "content_en": "- Project Status: On Track / At Risk / Delayed\n- Overall Progress: XX%\n- Key Highlights",
                "content_id": "- Status Proyek: Sesuai Jadwal / Berisiko / Tertunda\n- Progress Keseluruhan: XX%\n- Sorotan Utama",
            },
            {
                "layout": "content",
                "title_en": "Completed This Period",
                "title_id": "Selesai Periode Ini",
                "content_en": "- Task 1: Description\n- Task 2: Description\n- Task 3: Description",
                "content_id": "- Tugas 1: Deskripsi\n- Tugas 2: Deskripsi\n- Tugas 3: Deskripsi",
            },
            {
                "layout": "content",
                "title_en": "In Progress",
                "title_id": "Sedang Dikerjakan",
                "content_en": "- Task 1: XX% complete\n- Task 2: XX% complete\n- Task 3: XX% complete",
                "content_id": "- Tugas 1: XX% selesai\n- Tugas 2: XX% selesai\n- Tugas 3: XX% selesai",
            },
            {
                "layout": "content",
                "title_en": "Issues & Risks",
                "title_id": "Masalah & Risiko",
                "content_en": "- Issue 1: Description | Mitigation\n- Risk 1: Description | Mitigation",
                "content_id": "- Masalah 1: Deskripsi | Mitigasi\n- Risiko 1: Deskripsi | Mitigasi",
            },
            {
                "layout": "content",
                "title_en": "Next Period Plans",
                "title_id": "Rencana Periode Berikutnya",
                "content_en": "- Planned Task 1\n- Planned Task 2\n- Planned Task 3",
                "content_id": "- Rencana Tugas 1\n- Rencana Tugas 2\n- Rencana Tugas 3",
            },
        ],
    },
    "meeting_agenda": {
        "name_en": "Meeting Agenda",
        "name_id": "Agenda Rapat",
        "description_en": "Structured meeting agenda template",
        "description_id": "Template agenda rapat terstruktur",
        "slides": [
            {
                "layout": "title",
                "title_en": "Meeting Agenda",
                "title_id": "Agenda Rapat",
                "subtitle_en": "Meeting Topic | Date | Time",
                "subtitle_id": "Topik Rapat | Tanggal | Waktu",
            },
            {
                "layout": "content",
                "title_en": "Meeting Objectives",
                "title_id": "Tujuan Rapat",
                "content_en": "- Primary objective\n- Secondary objectives\n- Expected outcomes",
                "content_id": "- Tujuan utama\n- Tujuan sekunder\n- Hasil yang diharapkan",
            },
            {
                "layout": "content",
                "title_en": "Agenda Items",
                "title_id": "Item Agenda",
                "content_en": "1. Opening (5 min)\n2. Topic 1 (15 min)\n3. Topic 2 (15 min)\n4. Discussion (15 min)\n5. Action Items (5 min)\n6. Closing (5 min)",
                "content_id": "1. Pembukaan (5 menit)\n2. Topik 1 (15 menit)\n3. Topik 2 (15 menit)\n4. Diskusi (15 menit)\n5. Item Aksi (5 menit)\n6. Penutup (5 menit)",
            },
            {
                "layout": "content",
                "title_en": "Discussion Points",
                "title_id": "Poin Diskusi",
                "content_en": "- Point 1: Details\n- Point 2: Details\n- Point 3: Details",
                "content_id": "- Poin 1: Detail\n- Poin 2: Detail\n- Poin 3: Detail",
            },
            {
                "layout": "content",
                "title_en": "Action Items & Next Steps",
                "title_id": "Item Aksi & Langkah Selanjutnya",
                "content_en": "- Action 1: Owner | Deadline\n- Action 2: Owner | Deadline\n- Next meeting: Date",
                "content_id": "- Aksi 1: Penanggung Jawab | Tenggat\n- Aksi 2: Penanggung Jawab | Tenggat\n- Rapat berikutnya: Tanggal",
            },
        ],
    },
    "training": {
        "name_en": "Training Presentation",
        "name_id": "Presentasi Pelatihan",
        "description_en": "Educational and training material template",
        "description_id": "Template materi edukasi dan pelatihan",
        "slides": [
            {
                "layout": "title",
                "title_en": "Training Session",
                "title_id": "Sesi Pelatihan",
                "subtitle_en": "Topic | Trainer Name | Date",
                "subtitle_id": "Topik | Nama Trainer | Tanggal",
            },
            {
                "layout": "content",
                "title_en": "Learning Objectives",
                "title_id": "Tujuan Pembelajaran",
                "content_en": "By the end of this session, you will be able to:\n- Objective 1\n- Objective 2\n- Objective 3",
                "content_id": "Di akhir sesi ini, Anda akan mampu:\n- Tujuan 1\n- Tujuan 2\n- Tujuan 3",
            },
            {
                "layout": "content",
                "title_en": "Overview",
                "title_id": "Ringkasan",
                "content_en": "- Introduction to the topic\n- Why this matters\n- What we will cover today",
                "content_id": "- Pengenalan topik\n- Mengapa ini penting\n- Apa yang akan kita bahas hari ini",
            },
            {
                "layout": "content",
                "title_en": "Key Concepts",
                "title_id": "Konsep Utama",
                "content_en": "- Concept 1: Explanation\n- Concept 2: Explanation\n- Concept 3: Explanation",
                "content_id": "- Konsep 1: Penjelasan\n- Konsep 2: Penjelasan\n- Konsep 3: Penjelasan",
            },
            {
                "layout": "content",
                "title_en": "Step-by-Step Guide",
                "title_id": "Panduan Langkah demi Langkah",
                "content_en": "1. Step One\n2. Step Two\n3. Step Three\n4. Step Four",
                "content_id": "1. Langkah Satu\n2. Langkah Dua\n3. Langkah Tiga\n4. Langkah Empat",
            },
            {
                "layout": "content",
                "title_en": "Practice Exercise",
                "title_id": "Latihan Praktik",
                "content_en": "Exercise:\n- Instructions for hands-on practice\n- Expected outcome\n- Time allocated: XX minutes",
                "content_id": "Latihan:\n- Instruksi untuk praktik langsung\n- Hasil yang diharapkan\n- Waktu: XX menit",
            },
            {
                "layout": "content",
                "title_en": "Summary & Key Takeaways",
                "title_id": "Ringkasan & Poin Penting",
                "content_en": "- Key Point 1\n- Key Point 2\n- Key Point 3\n- Resources for further learning",
                "content_id": "- Poin Penting 1\n- Poin Penting 2\n- Poin Penting 3\n- Sumber untuk belajar lebih lanjut",
            },
            {
                "layout": "content",
                "title_en": "Questions?",
                "title_id": "Pertanyaan?",
                "content_en": "Thank you for participating!\n\nContact: trainer@email.com\nResources: link.to/resources",
                "content_id": "Terima kasih atas partisipasi Anda!\n\nKontak: trainer@email.com\nSumber: link.ke/sumber",
            },
        ],
    },
    "product_pitch": {
        "name_en": "Product Pitch",
        "name_id": "Pitch Produk",
        "description_en": "Product or startup pitch deck",
        "description_id": "Pitch deck produk atau startup",
        "slides": [
            {
                "layout": "title",
                "title_en": "Product Name",
                "title_id": "Nama Produk",
                "subtitle_en": "Tagline that captures your value proposition",
                "subtitle_id": "Tagline yang menggambarkan proposisi nilai Anda",
            },
            {
                "layout": "content",
                "title_en": "The Problem",
                "title_id": "Masalah",
                "content_en": "- What problem are you solving?\n- Who experiences this problem?\n- How big is this problem?",
                "content_id": "- Masalah apa yang Anda selesaikan?\n- Siapa yang mengalami masalah ini?\n- Seberapa besar masalah ini?",
            },
            {
                "layout": "content",
                "title_en": "Our Solution",
                "title_id": "Solusi Kami",
                "content_en": "- How we solve the problem\n- What makes us unique\n- Key benefits for users",
                "content_id": "- Bagaimana kami menyelesaikan masalah\n- Apa yang membuat kami unik\n- Manfaat utama bagi pengguna",
            },
            {
                "layout": "content",
                "title_en": "Product Demo",
                "title_id": "Demo Produk",
                "content_en": "- Key Feature 1\n- Key Feature 2\n- Key Feature 3\n- User Experience Highlights",
                "content_id": "- Fitur Utama 1\n- Fitur Utama 2\n- Fitur Utama 3\n- Highlight Pengalaman Pengguna",
            },
            {
                "layout": "content",
                "title_en": "Market Opportunity",
                "title_id": "Peluang Pasar",
                "content_en": "- Total Addressable Market (TAM)\n- Target Market\n- Growth Potential",
                "content_id": "- Total Addressable Market (TAM)\n- Target Pasar\n- Potensi Pertumbuhan",
            },
            {
                "layout": "content",
                "title_en": "Business Model",
                "title_id": "Model Bisnis",
                "content_en": "- How we make money\n- Pricing strategy\n- Revenue projections",
                "content_id": "- Bagaimana kami menghasilkan uang\n- Strategi harga\n- Proyeksi pendapatan",
            },
            {
                "layout": "content",
                "title_en": "Competition",
                "title_id": "Kompetisi",
                "content_en": "- Competitor landscape\n- Our competitive advantages\n- Why we will win",
                "content_id": "- Lanskap kompetitor\n- Keunggulan kompetitif kami\n- Mengapa kami akan menang",
            },
            {
                "layout": "content",
                "title_en": "The Team",
                "title_id": "Tim",
                "content_en": "- Founder 1: Background\n- Founder 2: Background\n- Key team members",
                "content_id": "- Founder 1: Latar Belakang\n- Founder 2: Latar Belakang\n- Anggota tim kunci",
            },
            {
                "layout": "content",
                "title_en": "The Ask",
                "title_id": "Permintaan",
                "content_en": "- What we are looking for\n- How funds will be used\n- Contact information",
                "content_id": "- Apa yang kami cari\n- Bagaimana dana akan digunakan\n- Informasi kontak",
            },
        ],
    },
}


def get_pptx_template(template_key: str) -> Optional[dict]:
    """
    Get a template by its key.

    Args:
        template_key: Template identifier (e.g., "blank", "business_proposal")

    Returns:
        Template dictionary or None if not found
    """
    return PPTX_TEMPLATES.get(template_key)


def get_pptx_template_list(lang: str = "en") -> list[dict]:
    """
    Get list of available templates with display info.

    Args:
        lang: Language code ("en" or "id")

    Returns:
        List of dicts with key, name, description
    """
    templates = []
    for key, template in PPTX_TEMPLATES.items():
        templates.append(
            {
                "key": key,
                "name": template.get(f"name_{lang}", template.get("name_en", key)),
                "description": template.get(
                    f"description_{lang}", template.get("description_en", "")
                ),
            }
        )
    return templates


def get_template_slides_text(template_key: str, lang: str = "en") -> str:
    """
    Get text representation of template slides.

    Args:
        template_key: Template identifier
        lang: Language code

    Returns:
        Formatted text of all slides
    """
    template = get_pptx_template(template_key)
    if not template:
        return ""

    lines = []
    for i, slide in enumerate(template["slides"], 1):
        layout = slide.get("layout", "content")
        title = slide.get(f"title_{lang}", slide.get("title_en", f"Slide {i}"))

        lines.append(f"--- Slide {i}: {title} ---")

        if layout == "title":
            subtitle = slide.get(f"subtitle_{lang}", slide.get("subtitle_en", ""))
            if subtitle:
                lines.append(f"Subtitle: {subtitle}")
        else:
            content = slide.get(f"content_{lang}", slide.get("content_en", ""))
            if content:
                lines.append(content)

        lines.append("")

    return "\n".join(lines)
