import os
import re
import time
from playwright.sync_api import sync_playwright

AUTH_FILE = ".auth_sessions/readawrite_state.json"

TARGETS = [
    {
        "aid": "ac04dda030fae1380e3aa7ac52f66762",
        "name": "ฟาร์มสาวปีศาจรัก",
        "subtitles": {
            1: "สู่โลกใหม่และไร่ศักดิ์สิทธิ์",
            2: "การพบพานสาวปีศาจคนแรก",
            3: "ปลูกพลังเวทบนผืนดิน",
            4: "กำแพงป้องกันแห่งศรัทธา",
            5: "การรุกกลับสู่น้ำตก",
            6: "เผชิญหน้าผู้มีอำนาจ",
            7: "ยุทธการแนวป้องกันผาหิน",
            8: "ชัยชนะและการปกป้องไร่ศักดิ์สิทธิ์"
        }
    },
    {
        "aid": "c9ba3d70c41e7b9e05e4d1110ec5b94e",
        "name": "จากน้องสาวสู่พี่ใหญ่_สายใยแห่งความรัก",
        "subtitles": {
            1: "การเปลี่ยนแปลงเริ่มต้น",
            2: "การปรับตัวและการเรียนรู้",
            3: "ความเครียดและความกดดัน",
            4: "การสร้างความสัมพันธ์และเชื่อมโยง",
            5: "การเผชิญหน้ากับความยากลำบากทางอารมณ์",
            6: "การเติบโตและความไวในการทำงาน",
            7: "การสร้างความผูกพันและเชื่อมโยงกับญาติ",
            8: "การเติบโตทางอารมณ์และการชดเชย"
        }
    },
    {
        "aid": "9e8c07991925a7993519a4d261fd6f2a",
        "name": "ดวงจันทร์แห่งเวทมนตร์_เรื่องราวของฮิลโคและเด็กสาวผู้เต้นระบำในความมืด",
        "subtitles": {
            1: "การพบกันของสายลับแห่งเวทมนตร์",
            2: "การทดลองลับ",
            3: "ภูติผีในชุมชน",
            4: "การสืบสวนครั้งแรก",
            5: "การสืบสวนที่เป็นปริศนา",
            6: "การสำรวจวัดเหนือธรรมชาติ",
            7: "ความจริงในวัดลี้ลับ",
            8: "ภูติผีที่ปรากฏอีกครั้ง"
        }
    }
]


def clean_story(page, target):
    aid = target["aid"]
    name = target["name"]
    subtitles = target["subtitles"]
    
    print(f"\n=======================================================")
    print(f" 🚀 กำลังจัดการเรื่อง: '{name}' (ID: {aid})")
    print(f"=======================================================")
    
    # 1. โหลดหน้ารายการตอน
    ch_url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=mainManageChapter"
    page.goto(ch_url, timeout=45000)
    page.wait_for_timeout(2500)
    
    rows = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.table tbody tr')).map((r, idx) => {
            const chk = r.querySelector('input[name=chk_chapter_guid]');
            const guid = chk ? chk.value : '';
            const title = chk ? chk.getAttribute('title_name') : '';
            const words = chk ? parseInt(chk.getAttribute('word_count') || '0') : 0;
            const rowStatus = r.getAttribute('status');
            const pubDate = r.getAttribute('first_published_date');
            const isPublished = (rowStatus === '2') || Boolean(pubDate && pubDate.length > 5);
            return { idx, guid, title, words, isPublished, rowStatus };
        }).filter(x => x.guid);
    }""")
    
    print(f"   📊 ตรวจพบทั้งหมด {len(rows)} ตอนในระบบ")
    
    # 2. แยกตอนที่เป็นแบบร่างซ้ำซ้อน (Stubs) ออกจากตอนจริง
    # ตอนที่เป็น Stub คือตอนที่ชื่อเป็น "ตอนที่ X: ตอนที่ X " และยังไม่ได้เผยแพร่ (words น้อย)
    stubs = []
    real_chapters = []
    
    for r in rows:
        title = r["title"].strip()
        m_stub = re.match(r"^ตอนที่\s*(\d+):\s*ตอนที่\s*\1\s*$", title)
        if m_stub and not r["isPublished"]:
            stubs.append(r)
        else:
            real_chapters.append(r)
            
    print(f"   🗑️ พบตอนร่างขยะที่ซ้ำซ้อน: {len(stubs)} ตอน")
    print(f"   ✨ พบตอนจริงที่มีเนื้อหา: {len(real_chapters)} ตอน")
    
    # ลบตอนที่เป็น Stub ทีละตอนผ่าน AJAX
    for s in stubs:
        guid = s["guid"]
        title = s["title"]
        print(f"      ❌ กำลังลบตอนร่างซ้ำ: '{title}' (GUID: {guid})...")
        res = page.evaluate("""(g) => {
            return new Promise((resolve) => {
                $.ajax({
                    method: "POST",
                    url: "?action=manage_chapter&token=",
                    data: {
                        chapter_guid: g,
                        manage: "delete",
                        is_collaborator: 0
                    },
                    dataType: "json"
                }).done((data) => {
                    resolve(data);
                }).fail((xhr) => {
                    resolve({error: xhr.statusText, status: xhr.status});
                });
            });
        }""", guid)
        success = res.get("status", {}).get("success", False)
        if success:
            print(f"         ✅ ลบสำเร็จ!")
        else:
            print(f"         ⚠️ การลบล้มเหลว: {res}")
        time.sleep(0.5)
        
    # 3. แก้ไขชื่อตอนจริง (real_chapters) ให้ถูกต้อง ไม่ให้มีชื่อย่อยซ้ำซ้อน
    print(f"\n   ✏️ ปรับแก้ชื่อตอนของตอนจริงให้สะอาดและถูกต้อง...")
    
    for r in real_chapters:
        guid = r["guid"]
        old_title = r["title"]
        m_num = re.search(r"ตอนที่\s*(\d+)", old_title)
        if not m_num:
            print(f"      ⚠️ ไม่สามารถระบุเลขตอนจาก: '{old_title}'")
            continue
        num = int(m_num.group(1))
        sub = subtitles.get(num, "")
        clean_full_title = f"ตอนที่ {num}: {sub}"
        
        print(f"      [ตอนที่ {num}] ปรับชื่อ: '{old_title}' -> '{clean_full_title}'")
        
        edit_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={aid}&chapter_id={guid}"
        page.goto(edit_url, timeout=45000)
        page.wait_for_timeout(2000)
        
        # ปิด Pop-up กู้คืนแบบร่างถ้ามี
        btn_cancel = page.locator("#btn_cancel_local_draft")
        if btn_cancel.is_visible():
            btn_cancel.click()
            page.wait_for_timeout(500)
            
        page.fill("#chapter_title", clean_full_title)
        page.fill("#chapter_subtitle", "")
        
        # กดบันทึกแบบร่าง
        page.click("#btnSaveDraft")
        page.wait_for_timeout(1000)
        
        # หากมี modal ให้เลือกเหตุผลการแก้ไข (สำหรับตอนที่เผยแพร่แล้ว)
        try:
            change_log_label = page.locator("label[for=pop_change_log2]")
            if change_log_label.is_visible(timeout=1500):
                change_log_label.click()
                page.wait_for_timeout(500)
                page.click(".swal2-modal input.btnSaveDraft")
                page.wait_for_timeout(2500)
            else:
                page.wait_for_timeout(1500)
        except Exception as e:
            print(f"         ℹ️ ไม่พบ modal หรือบันทึกปกติ: {e}")
            page.wait_for_timeout(1500)
            
        print(f"         ✅ บันทึกชื่อตอนที่ {num} สะอาดเรียบร้อย!")
        time.sleep(0.5)
        
    # 4. ตรวจสอบความถูกต้องขั้นสุดท้าย
    page.goto(ch_url, timeout=45000)
    page.wait_for_timeout(2500)
    final_rows = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.table tbody tr')).map(r => {
            const chk = r.querySelector('input[name=chk_chapter_guid]');
            const p = r.querySelector('.chapter_detail p, td:nth-child(3)');
            return {
                guid: chk ? chk.value : '',
                title: chk ? chk.getAttribute('title_name') : '',
                words: chk ? chk.getAttribute('word_count') : '',
                status: r.getAttribute('status'),
                display: p ? p.innerText.trim() : ''
            };
        }).filter(x => x.guid);
    }""")
    
    print(f"\n   📋 ผลการตรวจสอบสุดท้ายสำหรับ '{name}':")
    print(f"   จำนวนตอนทั้งหมด: {len(final_rows)} ตอน (คาดหวัง: 8 ตอน)")
    for fr in final_rows:
        print(f"      • Status: {fr['status']} | Words: {fr['words']:4s} | {fr['display']}")
    print(f"=======================================================\n")


def main():
    if not os.path.exists(AUTH_FILE):
        print("❌ ไม่พบ auth session file")
        return
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
        page = context.new_page()
        
        for target in TARGETS:
            clean_story(page, target)
            
        context.storage_state(path=AUTH_FILE)
        browser.close()
        print("🎉 ดำเนินการแก้ไขปัญหาบทซ้ำซ้อนเสร็จสิ้นสมบูรณ์ 100%!")


if __name__ == "__main__":
    main()
