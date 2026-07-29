# Aplikasi SPP Sekolah

![Fenrir v4](https://img.shields.io/badge/fenrir-v4-4F46E5?style=flat)
![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue?style=flat&logo=python)
![MongoDB Atlas](https://img.shields.io/badge/mongodb-atlas-green?style=flat&logo=mongodb)
![CI](https://img.shields.io/github/actions/workflow/status/IshikawaUta/aplikasi-spp-sekolah/.github/workflows/ci.yml?style=flat)
![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen?style=flat)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat)

Aplikasi manajemen pembayaran SPP berbasis web — data siswa, tagihan, pembayaran, virtual account Xendit, dan laporan keuangan. Dibangun dengan **Fenrir v4** (ASGI), **MongoDB Atlas**, dan **Tailwind CSS**.

---

## Fitur

### Dashboard
- Ringkasan statistik: total siswa, kelas, komponen, tagihan, pembayaran
- Grafik pembayaran per bulan
- Quick search siswa

### Master Data
- **Siswa** — CRUD, import batch dari Excel, kenaikan kelas massal
- **Kelas** — CRUD, filter per tahun akademik
- **Komponen** — komponen biaya (SPP, uang bangunan, dll) dengan tipe `bulanan` / `tahunan`
- **Periode** — tahun akademik, periode tagihan, konfigurasi tarif per komponen + angkatan

### Transaksi
- **Tagihan** — generate massal per kelas + komponen, batalkan, tandai lunas
- **Pembayaran** — input manual, multi-invoice, kwitansi cetak, void & koreksi
- **Virtual Account** — generate VA via Xendit (bank BCA, BNI, BRI, Mandiri), mark-paid manual, webhook callback

### Laporan
- Ringkasan pembayaran per tahun akademik
- Tunggakan per kelas + angkatan
- Mutasi pembayaran per rentang tanggal
- Kartu SPP per siswa
- Rekap harian
- Export Excel (semua format di atas)

### Admin
- Manajemen pengguna (admin/kasir)
- Ubah role, reset password, toggle aktif
- Koreksi: void pembayaran, edit nominal invoice
- Rekening bank

### Keamanan
- Autentikasi session-based + bcrypt password hashing
- CSRF protection di semua form POST
- Rate limiting login (5 percobaan per 15 menit)
- Role-based access: admin (full), kasir (terbatas)
- Security headers: X-Frame-Options, Content-Type, HSTS

---

## Tech Stack

| Layer | Teknologi |
|-------|-----------|
| Framework | [Fenrir v4](https://fenrir-framework.dev) (Python ASGI) |
| Database | MongoDB Atlas via [Motor](https://motor.readthedocs.io) (async driver) |
| Auth | Fenrir sessions + [bcrypt](https://pypi.org/project/bcrypt/) |
| Payment | Xendit Virtual Account (optional, fallback dummy VA) |
| Styling | Tailwind CSS via CDN |
| Export | openpyxl (Excel generation) |
| Markdown | markdown + bleach (XSS sanitization) |

---

## Quick Start

### Prasyarat
- Python 3.13+
- MongoDB Atlas (free tier cukup)
- (Opsional) Xendit API key untuk Virtual Account production

### Setup

```bash
git clone https://github.com/IshikawaUta/aplikasi-spp-sekolah.git
cd aplikasi-spp-sekolah
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — minimal isi `MONGO_URI`:

```env
SECRET_KEY=random-64-char-string
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=spp_fenrir
APP_TITLE="SPP SMA NEGERI 1 CONTOH"
APP_NAME="SMA NEGERI 1 CONTOH"
APP_ADDRESS="Jl. Pendidikan No. 1"
APP_PHONE="(021) 1234567"
FENRIR_DEV_MODE=1
```

### Run

```bash
source .venv/bin/activate
fenrir run app:app --port 8000 --dev
```

Buka `http://localhost:8000/auth/login`. First-run auto-create admin:

| Email | Password |
|-------|----------|
| `admin@spp.sch.id` | `admin123` |

---

## Struktur Proyek

```
.
├── app.py                  # Entry point — Fenrir app, middleware, template globals
├── config.py               # Env loader (python-dotenv)
├── models/                 # Data access layer (Motor + MongoDB)
│   ├── db.py               # Connection singleton, sequences, indexes
│   ├── user.py             # User auth, CRUD, seed_admin
│   ├── student.py          # Student CRUD + aggregate pipeline
│   ├── class_model.py      # Class CRUD
│   ├── component.py        # Fee component CRUD
│   ├── period.py           # Academic years, billing periods, fee configs
│   ├── invoice.py          # Invoice CRUD + mass generation
│   ├── payment.py          # Payment CRUD + void + lines
│   ├── virtual_account.py  # VA generation (Xendit + dummy), callback
│   ├── bank_account.py     # Bank account CRUD
│   ├── dashboard.py        # Dashboard aggregation queries
│   └── audit.py            # Audit trail logging
├── routes/                 # Route handlers (Fenrir Blueprint)
│   ├── auth.py             # Login/logout
│   ├── dashboard.py        # Dashboard + search
│   ├── master.py           # Siswa, kelas, komponen, periode
│   ├── tagihan.py          # Invoice generation + management
│   ├── pembayaran.py       # Payment + VA + kwitansi + webhook
│   ├── laporan.py          # Reports + Excel export
│   ├── admin.py            # User management + koreksi + bank accounts
│   └── decorators.py       # @login_required, @admin_required, @csrf_protect
├── services/               # Shared services
│   ├── csrf.py             # CSRF token gen + validation
│   ├── exporter.py         # Excel workbook helpers
│   └── ratelimit.py        # In-memory rate limiter
├── templates/              # Jinja2 templates (Tailwind CDN)
│   ├── base.html.j2        # Layout: navbar, sidebar, CSRF inject
│   ├── auth/               # Login page
│   ├── dashboard/          # Dashboard + search results
│   ├── master/             # Siswa, kelas, komponen, periode
│   ├── tagihan/            # Tagihan list, generate form
│   ├── pembayaran/         # Payment form, VA list, kwitansi
│   ├── laporan/            # Report pages
│   ├── admin/              # Pengguna, koreksi, rekening
│   └── errors/             # 404, 500 pages
├── tests/
│   ├── conftest.py         # Fixtures: mock_db, FenrirTestClient wrapper
│   ├── test_unit.py        # Unit tests (205 tests, no DB)
│   └── test_routes.py      # Route integration tests (with DB)
├── .env.example            # Template environment variables
├── .coveragerc             # Coverage config
├── pytest.ini              # Pytest config (asyncio auto, coverage)
├── vercel.json             # Vercel deployment config
├── requirements.txt        # Python dependencies
└── LICENSE                 # MIT
```

---

## API Endpoints

### Auth
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/auth/login` | - | Login page |
| POST | `/auth/login` | - | Process login |
| GET | `/auth/logout` | login | Logout |

### Dashboard
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/` | login | Dashboard statistics |
| GET | `/api/search-siswa` | login | AJAX student search |

### Master — Siswa
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/master/siswa` | login | List siswa |
| POST | `/master/siswa` | admin | Create siswa |
| POST | `/master/siswa/<id>/update` | admin | Update siswa |
| POST | `/master/siswa/<id>/delete` | admin | Delete siswa |
| GET | `/master/siswa/import` | login | Import form |
| POST | `/master/siswa/import` | admin | Process Excel import |
| GET | `/master/kenaikan-kelas` | login | Kenaikan kelas form |
| POST | `/master/kenaikan-kelas` | admin | Process kenaikan massal |

### Master — Kelas, Komponen, Periode
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/master/kelas` | login | List kelas |
| POST | `/master/kelas` | admin | Create kelas |
| POST | `/master/kelas/<id>/update` | admin | Update kelas |
| POST | `/master/kelas/<id>/delete` | admin | Delete kelas |
| GET | `/master/komponen` | login | List komponen |
| POST | `/master/komponen` | admin | Create komponen |
| POST | `/master/komponen/<id>/update` | admin | Update komponen |
| POST | `/master/komponen/<id>/delete` | admin | Delete komponen |
| GET | `/master/periode` | login | Periode (AY, billing, fee) |
| POST | `/master/periode/academic-year` | admin | Create academic year |
| POST | `/master/periode/academic-year/<id>/activate` | admin | Set active AY |
| POST | `/master/periode/academic-year/<id>/delete` | admin | Delete AY |
| POST | `/master/periode/billing-period` | admin | Create billing period |
| POST | `/master/periode/billing-period/<id>/update` | admin | Update period |
| POST | `/master/periode/billing-period/<id>/delete` | admin | Delete period |
| POST | `/master/periode/fee-config` | admin | Create/update fee config |
| POST | `/master/periode/fee-config/<id>/delete` | admin | Delete fee config |

### Tagihan
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/tagihan/` | login | List invoices |
| GET | `/tagihan/generate` | login | Generate form |
| POST | `/tagihan/generate` | admin | Generate mass invoices |
| POST | `/tagihan/<id>/update` | admin | Update invoice |
| POST | `/tagihan/<id>/cancel` | admin | Cancel invoice |
| POST | `/tagihan/<id>/paid-off` | admin | Mark invoice as paid off |

### Pembayaran & Virtual Account
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/pembayaran/` | login | List payments |
| POST | `/pembayaran/` | login | Create payment |
| GET | `/pembayaran/kwitansi/<payment_id>` | login | Printable receipt |
| GET | `/pembayaran/virtual-akun` | login | VA list |
| POST | `/pembayaran/virtual-akun/create` | admin | Generate VA |
| POST | `/pembayaran/virtual-akun/<va_id>/mark-paid` | admin | Mark VA paid manually |
| POST | `/pembayaran/virtual-akun/<va_id>/cancel` | admin | Cancel VA |
| POST | `/pembayaran/xendit-callback` | - | Xendit webhook |

### Laporan
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/laporan/` | login | Ringkasan pembayaran |
| GET | `/laporan/tunggakan` | login | Tunggakan per kelas |
| GET | `/laporan/mutasi` | login | Mutasi pembayaran |
| GET | `/laporan/kartu-spp` | login | Kartu SPP siswa |
| GET | `/laporan/rekap-harian` | login | Rekap harian |
| GET | `/laporan/export/siswa` | login | Export Excel siswa |
| GET | `/laporan/export/tunggakan` | login | Export Excel tunggakan |
| GET | `/laporan/export/rekap` | login | Export Excel rekap |

### Admin
| Method | Path | Auth | Deskripsi |
|--------|------|------|-----------|
| GET | `/admin/pengguna` | admin | List users |
| POST | `/admin/pengguna` | admin | Create user |
| POST | `/admin/pengguna/<id>/role` | admin | Change role |
| POST | `/admin/pengguna/<id>/password` | admin | Reset password |
| POST | `/admin/pengguna/<id>/toggle-active` | admin | Toggle active |
| GET | `/admin/koreksi` | admin | Correction page |
| POST | `/admin/koreksi/void-payment/<id>` | admin | Void payment |
| POST | `/admin/koreksi/edit-invoice/<id>` | admin | Edit invoice amount |
| GET | `/admin/rekening` | admin | List bank accounts |
| POST | `/admin/rekening` | admin | Create bank account |
| POST | `/admin/rekening/<id>/update` | admin | Update bank account |
| POST | `/admin/rekening/<id>/delete` | admin | Delete bank account |

---

## Testing

```bash
# Unit test (mock DB, no MongoDB needed)
pytest tests/test_unit.py -v --cov=models --cov=services --cov=config

# Full suite (butuh MongoDB Atlas)
pytest tests/ -v --cov=. --tb=short

# Lint + type check
ruff check .
mypy app.py routes/ models/ services/ --ignore-missing-imports
```

**205 tests, 90% coverage, 0 warnings.**

---

## Deployment

### Vercel

```bash
npm i -g vercel
vercel
```

Set env di dashboard Vercel (sama dengan `.env.example`).

### Railway / Render / Fly.io

Deploy from Git — auto-detected Python app. Set env via dashboard.

---

## Environment Variables

Selengkapnya di `.env.example`:

| Variable | Wajib | Default | Deskripsi |
|----------|-------|---------|-----------|
| `SECRET_KEY` | Ya | `dev-secret...` | Session encryption key |
| `MONGO_URI` | Ya | `localhost` | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | Tidak | `spp_fenrir` | Database name |
| `APP_TITLE` | Tidak | `Aplikasi SPP Sekolah` | App title (browser tab) |
| `APP_NAME` | Tidak | `Aplikasi SPP Sekolah` | School name (kwitansi) |
| `APP_ADDRESS` | Tidak | - | School address (kwitansi) |
| `APP_PHONE` | Tidak | - | School phone (kwitansi) |
| `XENDIT_API_KEY` | Tidak | - | Xendit API key (tanpa ini = dummy VA) |
| `XENDIT_CALLBACK_TOKEN` | Tidak | - | Xendit webhook verification |
| `FENRIR_DEV_MODE` | Tidak | `1` | Dev mode (HSTS disabled) |

---

## Collections MongoDB

Database: `spp_fenrir` (dikonfigurasi via `MONGO_DB_NAME`)

| Collection | Deskripsi |
|------------|-----------|
| `user_profiles` | Admin & kasir accounts |
| `students` | Data siswa (NIS, nama, kelas) |
| `classes` | Daftar kelas + jenjang |
| `components` | Komponen biaya (SPP, bangunan, dll) |
| `academic_years` | Tahun akademik |
| `billing_periods` | Periode tagihan (bulanan/tahunan) |
| `fee_configs` | Konfigurasi tarif per komponen + angkatan |
| `invoices` | Tagihan per siswa |
| `payments` | Riwayat pembayaran |
| `payment_lines` | Detail pembayaran per invoice |
| `virtual_accounts` | Virtual Account Xendit/dummy |
| `va_invoice_lines` | Invoice yang ditagih via VA |
| `bank_accounts` | Rekening bank sekolah |
| `audit_logs` | Audit trail semua aksi |
| `sequences` | Auto-increment counter |

---

## Lisensi

MIT © 2026 — lihat [LICENSE](LICENSE)
