# ProcureFlow - Procurement Document OS

## Overview

ProcureFlow is a full-stack procurement document management platform that automates document processing using OCR and AI extraction. It supports quotations, purchase orders, invoices, delivery orders, and purchase requisitions.

## Architecture

- **Frontend**: React 19 + Tailwind CSS, built with CRACO (Create React App Configuration Override), served on port 5000
- **Backend**: FastAPI (Python) + Motor (MongoDB async driver), served on port 8001
- **Database**: MongoDB (local instance on port 27017)
- **AI/LLM**: Gemini 2.5 Flash via `emergentintegrations` package for document classification and extraction
- **PDF Generation**: ReportLab

## Project Structure

```
.
├── backend/               # FastAPI backend
│   ├── server.py          # Main API entry point (1135 lines)
│   ├── services/          # Business logic (auth, OCR, AI, PDF, email)
│   ├── assets/            # Static assets for PDF generation
│   ├── uploads/           # Uploaded document storage
│   └── requirements.txt   # Python dependencies
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # Reusable UI components (Radix UI, shadcn-style)
│   │   ├── pages/         # Application views
│   │   ├── lib/           # API client, auth context, utilities
│   │   └── App.js         # Root component + routing
│   └── craco.config.js    # Webpack/devServer config (proxy, host settings)
├── start.sh               # Main startup script (MongoDB + backend + frontend)
└── node_modules/          # Root-level node_modules (react-scripts, craco)
```

## Running the Application

The app is started via `bash start.sh` which:
1. Starts MongoDB on port 27017 (data in `.mongodb/data/`)
2. Starts the FastAPI backend on port 8001 (localhost only)
3. Starts the React frontend on port 5000 (0.0.0.0, proxies `/api` to backend)

## Environment Variables

| Variable | Description |
|---|---|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | MongoDB database name (`procureflow`) |
| `JWT_SECRET` | JWT signing secret |
| `ADMIN_EMAIL` | Initial admin user email |
| `ADMIN_PASSWORD` | Initial admin user password |
| `FRONTEND_URL` | Frontend URL for CORS (backend) |
| `REACT_APP_BACKEND_URL` | Backend URL for frontend (empty = relative/proxy) |

## Key Features

- **RBAC**: Four roles - Admin, Manager, User, Viewer
- **AI Pipeline**: Auto-classification (PO/Invoice/DO/Quotation/PR) + structured data extraction
- **PDF Generation**: Branded document PDFs via ReportLab
- **Audit Logging**: Full action audit trail
- **Template Engine**: Customizable JSON schema per document type

## Package Management Notes

- Frontend packages are in **root-level** `node_modules/` (react-scripts, craco, all deps)
- Frontend's own `node_modules/` has some packages but react-scripts is removed to use root's
- Python packages in `.pythonlibs/`
- `emergentintegrations` installed from: https://d33sy5i8bnduwe.cloudfront.net/simple/

## Default Admin Credentials

- Email: `admin@procureflow.com`
- Password: `Admin123!`
