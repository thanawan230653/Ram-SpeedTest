# RAM SpeedTest (Speedtest-like GUI) — `ram_speedtest.py`

โปรแกรมทดสอบ **ความเร็ว RAM** (อ่าน/เขียน) แบบหน้าตา/ฟีลคล้าย **speedtest.net**  
กด **GO** แล้วโปรแกรมจะพยายามใช้ RAM ให้ **ใกล้ 100%** เพื่อทดสอบความเร็วแบบหนัก ๆ (stress test)

> ✅ ทำงานในเครื่องคุณเท่านั้น (Local only)  
> ❌ ไม่อัปโหลดไฟล์/ข้อมูลไปไหน


## คุณสมบัติ (Features)

- UI แบบ Speedtest: ปุ่ม **GO / STOP** + เกจแสดงความเร็ว
- ทดสอบ RAM แบบ “กินเต็มใกล้ 100%” อัตโนมัติ (ไม่ต้องเลือก GB)
- ตั้งเวลาเป็น **นาที** ได้ (เช่น 1, 2.5, 5 นาที)
- แสดงผลแบบเรียลไทม์:
  - **RAM SPEED (GB/s)** (รวมอ่าน+เขียน ณ ช่วงเวลานั้น)
  - **Write / Read (GB/s)**
  - % การใช้ RAM ของระบบ + RAM ที่เหลือ
- สรุปผลหลังจบ:
  - Average **Write / Read / Total (GB/s)**
  - Loops, checksum (ตรวจความถูกต้องการอ่าน)


## ข้อควรระวัง (สำคัญมาก)

โปรแกรมนี้ “กิน RAM หนักมาก” ตามสเปคที่ตั้งใจไว้  
อาจทำให้เกิดอาการต่อไปนี้ได้:

- เครื่องหน่วงมาก / หน้าจอค้างชั่วคราว
- โปรแกรมอื่นเด้ง/ปิดตัว
- Windows/Linux อาจ Swap/Pagefile หนัก (ช้าลงมาก)
- ถ้าระบบมี RAM น้อยหรือ Python 32-bit อาจจัดสรรไม่สำเร็จ (MemoryError)

> แนะนำ: ปิดโปรแกรมอื่นก่อนทดสอบ และใช้ Python 64-bit


## ความต้องการระบบ (Requirements)

- Python 3.8+ (แนะนำ 3.10+)
- แนะนำ **Python 64-bit**
- ทำงานได้บน Windows / Linux (และระบบที่มี Tkinter)

> **ตัวเลือกเสริม:** `psutil` (ช่วยให้ข้อมูล RAM/Process แม่นขึ้น)  
ติดตั้งได้ด้วย:
```bash
pip install psutil
```


## วิธีใช้งาน (Usage)

1) ดาวน์โหลดไฟล์ `ram_speedtest.py`  
2) เปิด Command Prompt / PowerShell / Terminal ในโฟลเดอร์ที่มีไฟล์  
3) รันโปรแกรม:
```bash
python ram_speedtest.py
```

### ในโปรแกรม

1) ใส่ **เวลาทดสอบ (นาที)** เช่น `1` หรือ `2.5`
2) กดปุ่ม **GO**
3) ระหว่างทดสอบจะเห็น:
   - เกจ “RAM SPEED” (GB/s) แบบเรียลไทม์
   - บรรทัด Write/Read
   - แถบเวลา + เหลือเวลา
4) ถ้าต้องการหยุดก่อนเวลา กด **STOP**
5) ดูสรุปผลในช่อง **สรุปผล (Summary)**


## อธิบายผลลัพธ์ (What the numbers mean)

- **Write (GB/s)**: ความเร็วเขียนข้อมูลลง RAM (ใช้ `memset` หรือการ fill buffer)
- **Read (GB/s)**: ความเร็วอ่านข้อมูลจาก RAM (คำนวณ checksum ด้วย `adler32`)
- **Total (GB/s)**: รวมอ่าน+เขียนจากเวลาที่ใช้จริง
- **Loops**: จำนวนรอบที่เขียน+อ่านครบหนึ่งครั้ง
- **Checksum**: ใช้ช่วยยืนยันว่าอ่านข้อมูลจริง (ไม่ใช่ค่าหลอก)

> หมายเหตุ: ผลลัพธ์ขึ้นกับ CPU/Memory controller/ความเร็ว RAM/การตั้งค่า BIOS/การทำงานของ OS และการ Swap


## ปัญหาที่พบบ่อย (Troubleshooting)

### 1) กด GO แล้วขึ้น MemoryError
- RAM ว่างไม่พอ / ระบบไม่ให้จัดสรร
- ลองปิดโปรแกรมอื่นก่อน
- ถ้าเป็น Python 32-bit ให้เปลี่ยนเป็น Python 64-bit

### 2) เครื่องหน่วงมาก
- เป็นปกติของโหมด “ใกล้ 100% RAM”
- รอให้ครบเวลาหรือกด STOP

### 3) เปิดไม่ได้ / ไม่มี Tkinter
- บาง Linux ต้องติดตั้งเพิ่ม เช่น:
  - Debian/Ubuntu:
    ```bash
    sudo apt-get install python3-tk
    ```


## สร้างไฟล์ .exe (Windows) (Optional)

ถ้าต้องการทำเป็น .exe แบบฟรี ใช้ **PyInstaller**:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed ram_speedtest.py
```

ไฟล์จะอยู่ในโฟลเดอร์ `dist/ram_speedtest.exe`

> หมายเหตุ: เครื่องอื่นที่รัน .exe **ไม่ต้องลง Python** (ถ้าสร้างแบบ onefile สำเร็จ)


## License

ใช้งานส่วนตัว/ทดสอบได้ตามสบาย (Local-only tool)
