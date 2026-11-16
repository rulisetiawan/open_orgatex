# OpenOrgaTEX - URL & Service Specification (100% OrgaTEX Parity)

Spesifikasi URL di bawah ini disesuaikan **100% identik dengan struktur URL asli OrgaTEX WebService (`WebService.exe`, `OtxWcfWebServiceLib.dll`, `BatchService`)**, sehingga sistem pihak ketiga (ERP, SAP, SCADA, Color Kitchen) yang sudah diprogram untuk OrgaTEX asli dapat langsung terhubung tanpa perlu mengubah path URL.

---

## 1. Port & Base Address Resmi OrgaTEX

* **Port Resmi OrgaTEX WebService:** `62324`
* **Base URL Resmi:** `http://<IP_SERVER_ORGATEX>:62324`
* **Port Alternatif (OpenOrgaTEX Default):** `8000` (atau `8788`)
* **Dokumentasi Interaktif (Swagger UI):** `http://<IP_SERVER_ORGATEX>:62324/docs`

> Untuk menjalankan backend langsung pada port resmi OrgaTEX 62324, cukup jalankan:
> ```cmd
> run_orgatex_exact_port.bat
> ```

---

## 2. Tabel Pemetaan URL (Exact OrgaTEX URL Parity)

### A. Alarm Configuration Controller (`WebService.Controllers.AlarmConfigurationController`)
Endpoint ini membaca data konfigurasi dari `conftext` dan `typeconf` OrgaTEX persis seperti binary aslinya:

| Method | URL Persis OrgaTEX | Deskripsi / Parameter |
| :--- | :--- | :--- |
| `GET` | `/api/alarmconfiguration/alarms/{language}/{machineGroupNo}` | Daftar seluruh alarm celup (cth: language: `en` atau `de`). |
| `GET` | `/api/alarmconfiguration/alarms/{language}/{machineGroupNo}/{alarmNo}` | Detail teks alarm spesifik berdasarkan nomor alarm. |
| `GET` | `/api/alarmconfiguration/alarmgroups/{language}/{machineGroupNo}` | Kategori / group alarm. |
| `GET` | `/api/alarmconfiguration/stopgroups/{language}/{machineGroupNo}` | Grup penghentian mesin (Operator stop, hold, dll). |
| `GET` | `/api/alarmconfiguration/functions/{language}/{machineGroupNo}` | Daftar fungsi kontroler SETEX 777 (Isi air, Panaskan, Tahan, Dosing, dll). |
| `GET` | `/api/alarmconfiguration/functionparameters/{language}/{machineGroupNo}` | Parameter teknis untuk setiap fungsi F-Code kontroler. |
| `GET` | `/api/alarmconfiguration/functiongroups/{language}/{machineGroupNo}` | Grup fungsi kontroler (Heating, Cooling, Dosing, Circulation). |
| `GET` | `/api/alarmconfiguration/resources/{language}/{machineGroupNo}` | Resource mesin (Main vessel, Circulation pump, Reel, Tank 1..N). |
| `GET` | `/api/alarmconfiguration/machineconstants/{language}/{machineGroupNo}/{mcNo}` | Konstanta mesin celup. |
| `GET` | `/api/alarmconfiguration/systemconstants/{language}/{machineGroupNo}` | Konstanta sistem OrgaTEX. |

---

### B. Batch Service (`OtxWcfWebServiceLib.BatchService` / `BatchPoolManager`)

Semua URL batch mendukung pemanggilan via `/api/BatchService/...` maupun `/BatchService/...`:

| Method | URL Persis OrgaTEX | Payload / Parameter Utama | Keterangan Integrasi ERP |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/BatchService/CreateBatch` | `BatchNo`, `MachineNo`, `ProgramNo`, `RecipeName`, `FlagBatchWeight`, `FlagLiquorAmount`, `CustomerInfo`, `ColorName`, `ColorNo` | **ERP -> OrgaTEX**: Inject Surat Perintah Kerja (SPK) lot celup baru. |
| `GET / POST` | `/api/BatchService/GetBatches` | Query/Body: `machineNo`, `status` | **ERP <- OrgaTEX**: Ambil daftar batch aktif & antrian mesin. |
| `GET` | `/api/BatchService/GetBatchesAsJson` | Query: `machineNo`, `status` | Mengambil seluruh batch dalam format JSON standar OrgaTEX. |
| `POST` | `/api/BatchService/ModifyBatch` | `BatchNo`, `FlagBatchWeight`, `FlagLiquorAmount`, `RecipeName` | Modifikasi data batch yang ada di antrian. |
| `POST` | `/api/BatchService/DeleteBatch` | `BatchNo` | Batalkan lot celup dari antrian (`CANCELLED`). |
| `POST` | `/api/BatchService/MoveBatch` | `BatchNo`, `TargetMachine`, `Position` | Pindah mesin celup atau ubah posisi nomor antrian. |
| `GET` | `/api/BatchService/GetBatchTemplate` | - | Mengambil template struktur parameter batch standar. |

---

### C. Web Monitoring & Online Status Service (`IWebMonitoringService` / `IOnlineStatusService`)

| Method | URL Persis OrgaTEX | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/WebMonitoringService/GetWebControllerStates` | **Live Status**: Status realtime kontroler SETEX (Online/Offline, Suhu aktual, Step aktif, Lot yang sedang jalan). |
| `GET` | `/api/WebMonitoringService/GetMachines` | Daftar master mesin celup beserta kapasitas Kg dan tipe kontrolernya. |
| `GET` | `/api/WebMonitoringService/GetMachineGroups` | Daftar grup mesin (High Temp Jet, Atmospheric, dll). |
| `GET` | `/api/OnlineStatus/GetOnlineControllerInfo` | Informasi IP, port, dan konektivitas kontroler online. |

---

### D. Recipe & Program Service (`RDM` / `EDX300`)

| Method | URL Persis OrgaTEX | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/RecipeService/GetRecipes` | Sinkronisasi master resep celup, zat pewarna & takaran kimia dosing. |
| `GET` | `/api/RecipeService/GetRecipeById?recipeId={id}` | Ambil detail 1 resep celup spesifik. |
| `GET` | `/api/ProgramService/GetPrograms` | Ambil master daftar program mesin celup SETEX 777 (`M_xxxx.PRG`). |

---

## 3. Contoh Request Persis Sesuai OrgaTEX WebService

### 1. Injeksi Batch Baru (`POST /api/BatchService/CreateBatch`)
```http
POST http://localhost:62324/api/BatchService/CreateBatch HTTP/1.1
Content-Type: application/json

{
  "BatchNo": "PJT026-LOT",
  "MachineNo": "TD12",
  "ProgramNo": 401,
  "RecipeName": "Reactive Violet 30S",
  "CustomerInfo": "PT. ARTA PERMAI",
  "ColorName": "UNGU TUA",
  "ColorNo": "1650159",
  "FlagBatchWeight": 350.0,
  "FlagLiquorAmount": 8.0,
  "BatchText_01": "CM 30S RIB",
  "ForceCreateReDye": false
}
```

### 2. Monitoring Status Kontroler (`GET /api/WebMonitoringService/GetWebControllerStates`)
```http
GET http://localhost:62324/api/WebMonitoringService/GetWebControllerStates HTTP/1.1
```
**Response:**
```json
[
  {
    "MachineNo": "TD12",
    "ControllerType": "SECOM777",
    "OperationalStatus": "RUNNING",
    "CurrentBatchNo": "PJT026-LOT",
    "CurrentStepNo": 12,
    "ActualTemp": 98.5,
    "IpAddress": "192.168.1.102",
    "IsOnline": true
  }
]
```

### 3. Mengambil Konfigurasi Alarm (`GET /api/alarmconfiguration/alarms/en/1`)
```http
GET http://localhost:62324/api/alarmconfiguration/alarms/en/1 HTTP/1.1
```
