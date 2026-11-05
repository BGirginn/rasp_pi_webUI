# Pi Control — Teknik denetim ve doğrulama

Tarih: 5 Kasım 2026 · Kaynak: `b763ede` · Başlangıç Git durumu temizdi.

Proje tek Raspberry Pi'nin sistemini web üzerinden yönetiyor. Varsayılan yük tek yönetici, tek agent ve birkaç tarayıcı oturumu. ECC production-audit ve Ponytail audit yaklaşımıyla giriş noktaları, UI etkileşimleri, yetki sınırları, veri yazma, job/backup/restore, kurulum ve testler incelendi. NAS veya versiyon kontrolü uygulaması kapsam dışı.

**Üretime hazırlık değerlendirmesi: 58/100 — riskli.** Bu ölçülmüş bir kalite puanı değil, aşağıdaki bulgulara dayalı önceliklendirme kararıdır. Dosya kökü dışına yazma ve restore sırasında veri kaybı kapanmadan dosya/restore yetenekleri genişletilmemeli. Tasarım ve işlev planı [ana rapordadır](IMPROVE_UPGRADE_REPORT.md).

Kanıt türleri: **Yeniden üretildi** yerel ve geçici verilerle çalıştırılmıştır; **kaynakla doğrulandı** yürütme yolunda görülen davranıştır; **canlı doğrulanmadı** Pi'deki kurulum veya fiziksel sonuç hakkında iddia değildir.

## Önce düzeltilmesi gerekenler

### 1. Upload kayıtlı kökün dışına yazabiliyor — kritik, yeniden üretildi

- **İşlev:** `panel/api/routers/files.py:246–263` yükleme dizinini denetliyor.
- **Sorun:** Son dosya yolu denetlenmeden `open(..., "wb")` kullanılıyor. İzinli dizindeki mevcut symlink, servis hesabının yazabildiği dışarıdaki dosyaya yönelirse operator/admin o dosyayı değiştirebiliyor. Bu, root erişimi elde edildiği iddiası değildir.
- **En küçük tam düzeltme:** Son hedefi ve kök sınırını doğrula; symlink izlemeyen, yarışa dayanıklı açma ve geçici dosyadan atomik yerleştirme uygula. Aynı hedef politikası copy/move/rename için de incelenmeli.
- **Ertelenirse:** UI kısıtlarına rağmen proje dışındaki kullanıcı dosyaları değiştirilebilir. Kontrol edilmiş kök ve dış dosyayla sonuç: `UPLOAD_CHANGED_FILE_OUTSIDE_REGISTERED_ROOT= True`.

### 2. Snapshot restore `.git` ve diğer dışlanan içeriği siliyor — kritik, yeniden üretildi

- **İşlev:** `services/project_service.py:49–124`; varsayılan dışlamalar `routers/projects.py:25`.
- **Sorun:** Snapshot `.git`, `.venv`, `dist`, `node_modules` ve linkleri dışlıyor. Restore tüm kökü staging ile değiştirip önceki kökü siliyor. Otomatik pre-restore snapshot da aynı dışlamaları kullandığından bu içerik ondan geri getirilemiyor.
- **En küçük tam düzeltme:** Restore'un koruyacağı yerel içeriği açıkça tanımla; doğrulama tamamlanana kadar önceki kökü koru. İlgisiz dosyaları sessizce birleştiren bir restore da eski dosyaları bırakacağından doğru çözüm değildir; restore politikası testle sabitlenmeli.
- **Ertelenirse:** Restore başarılı görünürken yerel Git geçmişi ve dışlanan dosyalar kaybolur. Sonuç: `GIT_DIRECTORY_PRESENT_AFTER_RESTORE= False`.

### 3. Admin console safe mode çalıştırılabilir argümanları engellemiyor — yüksek, yeniden üretildi

- **İşlev:** `routers/admin_console.py:159–198` → `agent/pi-agent.py:256`.
- **Sorun:** Komut prefix/sub-string ile kabul ediliyor. `find . -exec /usr/bin/true {} ;` safe modda agent'a iletildi; testte RPC mock kullanıldı, root komut çalıştırılmadı. Gerçek `find -exec` başka program çalıştırabilir; `systemctl` gibi geniş komut adları da salt okunur politika sağlamaz.
- **En küçük tam düzeltme:** Shell metni yerine argv üzerinden açık altkomut ve argüman politikası uygula; aynı sınırı root agent doğrulasın. Timeout ve çıktı boyutu da sınırlansın.
- **Ertelenirse:** Admin hesabı safe/risky ayrımını aşarak root agent üzerinden beklenmeyen işlem yapabilir. Sonuç: `SAFE_MODE_FORWARDED_EXEC_CAPABLE_FIND= True`.

### 4. PTY oturumuna yeniden bağlanırken sahiplik denetlenmiyor — yüksek, kaynakla doğrulandı

- **İşlev:** `routers/terminal.py:760–773`, `active_sessions` içindeki `session_id` ile reattach.
- **Sorun:** İstekteki session ID mevcutsa `session.user_id` ile oturum açan kullanıcı karşılaştırılmıyor. Geçerli full-mode/break-glass yetkisi olan başka bir kullanıcı ID'yi biliyorsa aynı shell'e bağlanabilir; bu anonim erişim değildir.
- **En küçük tam düzeltme:** Reattach öncesi sahiplik denetimi; izin verilmeyen ID için ret. Açık oturum boyunca yetki süresinin uygulanması ayrıca kontrol edilmeli.
- **Ertelenirse:** Kullanıcılar arasında shell girdisi ve terminal çıktısı karışabilir. İki kullanıcıyla canlı WebSocket deneyi yapılmadı.

### 5. Uygulama update'i agent bağımlılıklarını kurmuyor — yüksek, kaynakla doğrulandı

- **İşlev:** `agent/jobs/handlers.py:518–566` temiz release/venv hazırlayıp iki servisi başlatıyor.
- **Sorun:** Yeni venv'e yalnız API requirements kuruluyor. Agent'ın `paho-mqtt`, `asyncio-throttle`, native D-Bus/GObject gibi ayrı gereksinimleri kapsam dışı kalıyor. Ayrıca `install_user` ve socket group varsayımları `fou4` hesabına bağlı.
- **En küçük tam düzeltme:** Hedef Pi'nin runtime ve native gereksinimleriyle iki bileşeni birlikte doğrula; kurulum kullanıcısını tek gerçek yapılandırmadan al; release'i ancak API ve agent kontrolleri geçince etkinleştir.
- **Ertelenirse:** API health başarılı olduğu halde agent veya bazı özellikler çalışmayabilir. Pi'de yeni release başlatılmadı.

### 6. Release yedeği çalıştırılabilir restore için eksik — yüksek, kaynakla doğrulandı

- **İşlev:** `agent/jobs/handlers.py:184–195` release içinden `venv`, `node_modules`, `dist` dışlıyor; `scripts/restore_helper.py:100–111` kopyalayıp `current` yapıyor.
- **Sorun:** Restore helper bu artefaktları kurmuyor veya önceki venv'i bağlamıyor. Servisler `current/venv/bin/...` bekliyor; Caddy de `dist` bekliyor. Kaynak yedeği, doğrudan çalıştırılabilir release yerine geçmiyor.
- **En küçük tam düzeltme:** Kaynak restore ile çalışan release restore'u ayır; hazırlama/bağımlılık/UI build ve doğrulamayı symlink geçişinden önce tamamla. Önceki release rollback için tutulmalı.
- **Ertelenirse:** Release bileşeniyle kurtarma, servis açılmaması ve geri dönüşle sonuçlanabilir. Gerçek bakım/restore çalıştırılmadı.

### 7. Eski update yolu atomik release düzeniyle uyuşmuyor — yüksek, kaynakla doğrulandı

- **İşlev:** `scripts/update.sh:154–195,253–282` ve `.github/workflows/deploy.yml:59–65`.
- **Sorun:** Script `/opt/pi-control` altında doğrudan kaynak bekliyor; `.git` yoksa `rsync --delete`, varsa `git reset --hard` çalıştırıyor. `current/releases` düzenini aynı biçimde yönetmiyor. Backup canlı WAL DB'lerini düz `cp` ile alıyor. CI'daki `migrations backup ...` komutu da bir backup CLI'si değil; modül ilk argümanı DB yolu sayıyor ve `|| true` hatayı gizliyor.
- **En küçük tam düzeltme:** Kurulum/CLI/CI tek release hazırlama-etkinleştirme yoluna bağlansın. SQLite backup API kullanılsın; yedek ve doğrulama başarısızsa güncelleme başlamasın.
- **Ertelenirse:** Yerel değişiklikler veya release dizinleri zarar görebilir; yedeğin geçerli olduğu bilinmeden deploy yapılabilir. Bu scriptler çalıştırılmadı.

### 8. JWT yapılandırması güvenli biçimde hata vermiyor — yüksek, kaynakla doğrulandı

- **İşlev:** `panel/api/config.py:27,100–105`; `install.sh:371–382,386–408`.
- **Sorun:** Secret dosyası yoksa bilinen varsayılan değere dönülüyor. Taze kurulumda root'un oluşturduğu `0600` JWT dosyası servis kullanıcısına devredilmiyor; bu yolda secret okumak permission hatası verebilir. Health endpoint secret okumadığı için kurulum kontrolü bunu yakalamaz.
- **En küçük tam düzeltme:** Üretim startup'ında secret varlığı, boş/varsayılan olmaması ve okunabilirliği denetlensin. Dosya yalnız servis hesabına gerekli erişimi verecek sahiplik/izinle kurulsun; dünya-okunur yapılmasın.
- **Ertelenirse:** Kurulum sağlıklı görünürken login bozulabilir; eksik secret yapılandırmasında tahmin edilebilir anahtar kullanılabilir. Hedef Pi dosya izinleri canlı görülmedi.

### 9. SYSTEM servis politikası belgelenen korumadan daha geniş — yüksek, kaynakla doğrulandı

- **İşlev:** `routers/resources.py:148–151,351–397` ve `agent/providers/base.py:205–215`.
- **Sorun:** API admin/operator için SYSTEM'e start/stop/restart sunuyor; agent SYSTEM için enable/disable dahil daha fazlasını kabul ediyor. `docs/SECURITY_LIMITS.md` ise yalnız admin restart diyor. Agent'a çağıranın rolü iletilmiyor.
- **En küçük tam düzeltme:** CORE/SYSTEM/APP eylem politikası API ve agent'ta eşitlensin; rol sınırı API'de zorunlu olsun; aynı matris üzerinden UI yetenekleri dönsün.
- **Ertelenirse:** Operator, belgede korunduğu söylenen bazı SYSTEM servislerini durdurabilir. CORE korumasının tümü yok sayılıyor iddiası değildir.

### 10. Dosya ekranının başlangıcı ve kilidi API modeliyle uyuşmuyor — yüksek işlev açığı, kaynakla doğrulandı

- **İşlev:** `FilesPage.jsx:19–20,176–194,355–359`; `routers/files.py`, `project_service.py:37–45`.
- **Sorun:** Başlangıç `/home`, Home `/`; API yalnız kayıtlı kökleri kabul ediyor. Hiç kök yoksa ekran doğrudan 403 verir. “Unlock” yalnız frontend state'idir; dosya mutation API'leri OS parola doğrulamasına bağlı değildir. UI operator erişimini de saklarken API operator'a izin veriyor.
- **En küçük tam düzeltme:** Mevcut `/files/roots` ile başlangıç ve kök seçimi; rol politikasıyla tutarlı UI. Kilit güvenlik özelliğiyse sunucuda kısa süreli yetkiyle uygulanmalı, yalnız UX kilidiyse güvenlik iddiası kaldırılmalı.
- **Ertelenirse:** Dosya yöneticisi ilk açılışta kullanılamaz veya yanıltıcı bir koruma gösterir. Mevcut kopyala/taşı API'leri için UI akışı da tamamlanmalı.

### 11. Snapshot yolu API'yi bloke ediyor ve depolama sınırı yok — yüksek, kısmen yeniden üretildi

- **İşlev:** `project_service.py:49–87`, `routers/projects.py:25,59–63`.
- **Sorun:** Sıkıştırma/hash/dizin değiştirme async route içinde senkron çalışıyor; büyük kök event loop'u bloke edebilir. Boyut/retention/kilit yok. `node_modules` dışlaması yalnız kökte eşleşiyor; `.env` varsayılan olarak dışlanmıyor. Kök yolu kullanım anında allowlist'e karşı yeniden denetlenmiyor.
- **En küçük tam düzeltme:** Dosya işlemini mevcut job altyapısına taşı; proje başına kilit, kapasite ve saklama sınırı koy; dışlamaları açık tanımla, gizli içerik için kapsamı göster ve snapshot dosya izinlerini sınırla. Kökü her işlemde doğrula.
- **Ertelenirse:** Panel geçici olarak cevap vermez, disk dolar veya beklenmeyen hassas içerik arşivlenir. Geçici örnekte `SNAPSHOT_NESTED_DEPENDENCY_INCLUDED= True`, `SNAPSHOT_ENV_INCLUDED= True`; yük testi yapılmadı.

## Sonraki düzeltmeler

### 12. Dashboard veri yokken sıfır/bağlı gösterebiliyor — kaynakla doğrulandı

- **İşlev:** `DashboardContext.jsx:25–40,88–95,317–324`; `Sidebar.jsx` profile bölümü.
- **Sorun:** Eksik metrikler `|| 0` ile geçerli sıfır ölçümüne dönüşüyor; profil etiketi sabit `Connected`.
- **Düzeltme:** `null/unknown`, son gözlem zamanı ve API/agent erişimini ayrı işle. İlk grafik örneklerini sahte sıfırlarla doldurma.
- **Ertelenirse:** Veri kaybı, gerçek sıfır yük veya sağlıklı bağlantı sanılabilir.

### 13. Kaynak filtreleri provider belirtilmeyince uygulanmıyor — kaynakla doğrulandı

- **İşlev:** `routers/resources.py:77–84,123`.
- **Sorun:** `resource_class`/`managed` için `filtered` hesaplanıyor; `provider=None` dönüşünde bunun yerine filtrelenmemiş `live_services` kullanılıyor.
- **Düzeltme:** Aynı filtrelenmiş listeyi birleşik dönüşte kullan; provider yokken filtre senaryosunu test et.
- **Ertelenirse:** Kullanıcının seçimiyle liste içeriği uyuşmaz; servis yönetimi güvenilmez görünür.

### 14. Rollback olmuş job Pending etiketine düşüyor — kaynakla doğrulandı

- **İşlev:** `panel/ui/src/pages/Jobs.jsx:34–60`; agent'ta `JobState.ROLLED_BACK` var.
- **Sorun:** `stateMeta` içinde `rolled_back` yok; fallback `pending`.
- **Düzeltme:** Rollback için açık etiket/stil ekle. Bakım helper'larının health doğrulanmadan `completed` yazması da tamamlanma semantiğiyle birlikte düzeltilmeli.
- **Ertelenirse:** Geri alınmış veya hâlâ doğrulanan işlem kullanıcıya yanlış durumda sunulur.

### 15. Kalite kapıları gerçekte iddia ettikleri kadar güçlü değil — kaynakla ve komutla doğrulandı

- **İşlev:** API/agent `mypy.ini`, `.github/workflows/ci.yml`, `panel/ui/package.json`, `test_get_surface.py:97–100`.
- **Sorun:** İki MyPy config'inde `ignore_errors=True`; “Success” tip hatalarının olmadığı kanıtı değil. CI UI testlerini ve module reachability kontrolünü çalıştırmıyor. Installer Node 18'i yeterli sayıyor; lockfile Vite 8.1.4 ve ESLint 10.8.0'ın engine şartları daha yüksek. Testler FastAPI'nin iç `ModelField.required` özelliğine bağımlı; mevcut venv'deki sürüm sapmasında 29 test kırıldı.
- **Düzeltme:** Hedef runtime'ı installer/CI/local için eşitle; UI test ve modül kontrolünü CI'a ekle; MyPy'ı mevcut hataları görünür kılarak kademeli sıkılaştır; endpoint testlerinde iç alanlara bağımlılığı azalt. Kontrolleri geçirtmek için test silme veya gevşetme yapılmamalı.
- **Ertelenirse:** Yeşil lint/CI eksik güvence verir. Vite'ın resmî Node şartları: [Vite rehberi](https://vite.dev/guide/). Yerel Node 26 testi, Pi'deki Node 18/20 uyumluluğunu kanıtlamaz.

### 16. Preflight başarısızlığının çıkış kodu kayboluyor — yeniden üretildi

- **İşlev:** `install.sh:157–173`, başarısız `if` sonrasında `status=$?`.
- **Sorun:** Else kolu olmayan başarısız `if` ifadesinin kendisi burada 0 döndürüyor. Script gerçek preflight kodunu kaybedip “unexpected status 0” yolundan başarılı çıkabilir; kurulum tamamlanmaz.
- **Düzeltme:** Başarısız komutun kodunu `else` içinde al; 1/2 ve beklenmeyen durumları küçük bir shell testiyle doğrula.
- **Ertelenirse:** Otomasyon kurulumu yanlışlıkla başarılı sayabilir. `/bin/bash -c 'if false; then exit 9; fi; status=$?; printf "preflight_status_after_failed_if=%s\n" "$status"'` çıktısı: `preflight_status_after_failed_if=0`.

### 17. Bağımlılık güncellemesi araç zincirini de kapsamalı — canlı registry taraması

- **İşlev:** `panel/ui/package-lock.json`, `panel/api/requirements.txt:9–12`.
- **Sorun:** `npm audit` 15 etkilenen paket raporladı: 6 high, 9 moderate. `--omit=dev` sonucunda 0 bulgu var; dev-server/build araçlarındaki advisories, yayımlanmış statik UI'da aynı açığın erişilebilir olduğu anlamına gelmez. API `python-jose==3.3.0` sabitliyor; proje release notlarında güvenlik düzeltmeleri mevcut.
- **Düzeltme:** Dev araçlarını uyumlu sürümlerle birlikte güncelle ve test/build'i tekrarla; kör `npm audit fix --force` uygulama. JWT için mevcut PyJWT kullanımını temel alarak tek kütüphaneye geçiş değerlendir; HS256 allowlist korunmalı. Sırf sürüm eski diye algoritma-confusion açığının mevcut HS256 yolunda sömürülebildiği iddia edilmiyor.
- **Ertelenirse:** Geliştirme/CI yüzeyindeki bilinen riskler ve iki JWT kütüphanesiyle bakım yükü sürer. [python-jose resmî release notları](https://github.com/mpdavis/python-jose/releases). Python bağımlılık ağacının tam CVE taraması çalıştırılmadı.

### 18. Belgeler ve ufak tekrarlar bakım kararlarını yanıltıyor — kaynakla doğrulandı

- **İşlev:** `README.md`, `docs/THREAT_MODEL.md`, `docs/SECURITY_LIMITS.md`, `FilesPage.jsx:117–161`, `panel/ui/vite.config.js`.
- **Sorun:** README varsayılan admin parolası ve Drive'ın kapalı olduğu bilgisini veriyor; kod rastgele başlangıç parolası/ortam şartı ve Drive endpoint'leri içeriyor. Threat model bazı kontrolleri uygulanmış gösterirken gerçek sınırlar farklı. Yerel Vite proxy 8000, README API 8080. Dosya delete/mkdir/rename sonrasında aynı fetch iki kez çağrılıyor.
- **Düzeltme:** Güvenlik tablolarını “uygulandı/test edildi/planlandı” kanıtıyla güncelle; dev portunu eşitle; yinelenen üç fetch çağrısını sil. Mevcut format helper'larıyla yeni tekrar eklenmesin.
- **Ertelenirse:** Yanlış kurulum/güvenlik varsayımı ve gereksiz istekler sürer. Doğrulanan asgari sadeleştirme: **−3 satır, −0 dependency**; uygulama yapılmadı.

## Doğrulama kayıtları

Ortam: macOS arm64, Python 3.14.10, Node 26.13.0. CI Python 3.11 kullanıyor; fiziksel Pi runtime'ı bilinmiyor. Var olan `.venv` değiştirilmedi; ikinci tur için `/tmp/pi-control-audit-20261105-venv` oluşturulup `requirements-dev.txt` kuruldu. UI'da lockfile ile `npm ci --ignore-scripts --no-audit --no-fund` çalıştırıldı; kaynak/lockfile değişmedi.

| Kontrol | Sonuç |
|---|---|
| `npm run check:modules` | 46 production modülü erişilebilir |
| `npm run lint` | Geçti |
| `npm test` | 9 dosya, 60 test geçti |
| `npm run build` | Vite 8.1.4 build geçti |
| API ve agent `ruff check .` | İkisi de geçti |
| API ve agent `mypy --ignore-missing-imports .` | 63 / 36 dosya için Success; `ignore_errors=True` nedeniyle sınırlı güvence |
| Mevcut venv `pip check` | `No broken requirements found.`; requirements dosyasındaki pinlerle aynı olduğu anlamına gelmez |
| Mevcut venv API pytest | 339 geçti, 29 başarısız; aşağıdaki sürüm uyumsuzluğu |
| Mevcut venv agent pytest | Collection hatası: Docker SDK eksik; aşağıda |
| Requirements ile kurulan geçici ortam: API pytest | **368 geçti**, 1 üçüncü taraf deprecation uyarısı; 50,86 sn |
| Requirements ile kurulan geçici ortam: agent pytest | **149 geçti**; 2,58 sn |
| Shell `bash -n` | install/deploy/upload/update/preflight/health/uninstall sözdizimi geçti |
| `npm audit --json` | 15 paket: 6 high, 9 moderate |
| `npm audit --omit=dev --json` | 0 |
| Geçici veriyle davranış deneyi | Snapshot kaybı, upload symlink, safe console geçişi ve dışlama sorunları yeniden üretildi |

İlk API komutu: `cd panel/api && .venv/bin/python -m pytest --basetemp=/tmp/pi-audit-api-20261105`. Mevcut venv FastAPI 0.128.5 kullanıyordu; requirements 0.128.0 istiyor. Hata ayrıca tek test dosyasıyla tekrarlandı:

```text
tests/test_get_surface.py:100: in test_every_non_streaming_get_route_avoids_internal_errors
    if field.required
E   AttributeError: 'ModelField' object has no attribute 'required'
======================= 29 failed, 339 passed in 50.47s ========================
```

İlk agent komutu: `cd agent && ../panel/api/.venv/bin/python -m pytest --basetemp=/tmp/pi-audit-agent-20261105`:

```text
from providers.docker_provider import DockerException, DockerProvider, NotFound
E   ImportError: cannot import name 'DockerException' from 'providers.docker_provider'
ERROR tests/test_docker_provider.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

Bu hata requirements-dev'teki Docker SDK'nin mevcut venv'de kurulu olmamasıyla ilişkili; doğrudan Pi'de Docker servisinin bozuk olduğu anlamına gelmez.

İkinci turda test silinmeden veya atlanmadan iki tam suite geçti. Komutlar ve son satırlar:

```sh
cd panel/api
/tmp/pi-control-audit-20261105-venv/bin/python -m pytest --basetemp=/tmp/pi-audit-api-clean-20261105
# 368 passed, 1 warning in 50.86s
cd ../../agent
/tmp/pi-control-audit-20261105-venv/bin/python -m pytest --basetemp=/tmp/pi-audit-agent-clean-20261105
# 149 passed in 2.58s
```

Uyarı `starlette/testclient.py` içindeki `anyio.abc.BlockingPortal` deprecated alias'ına ait. Bu test turu requirements ile kurulan macOS/Python 3.14 ortamını doğrular; CI Python 3.11 veya fiziksel Pi kabulü yerine geçmez. Toplam **577 test** geçti: API 368 + agent 149 + UI 60. Yeşil suite yukarıdaki yeniden üretilmiş, henüz test kapsamına alınmamış kusurları ortadan kaldırmıyor.

Tarayıcıyla yerel UI incelemesi denendi. ECC Chrome aracı `Could not find Google Chrome executable for channel 'stable'`; diğer browser yüzeyi `The browser access host is unavailable` döndürdü. Yerel Vite sunucusu kapatıldı. Güncel sayfa görüntüsü ve gerçek tıklama kabulü yok.

## İnceleme sınırları

230 tracked dosyanın tamamının satır satır incelendiği iddia edilmiyor. Derin inceleme auth, dosyalar, projeler/snapshot, resources, terminal, RPC, jobs, backup/restore/update, kurulum/CI ve ana UI akışlarına yöneldi. Ağ/provider, IoT/MQTT, DNS, telemetri ve bildirimlerde giriş noktaları, konfigürasyon ve testler tarandı; tüm platform dalları ve her etkileşim tüketilmedi.

Pi'ye SSH bağlantısı, remote CI durumu, deployment, firmware flash, disk format/mount, ağ değişikliği, gerçek Drive yükleme veya restore yapılmadı. ESP örneklerinin elektriksel/firmware doğrulaması, fiziksel disk/USB davranışı, yük testi, tam Python CVE taraması ve güncel görsel erişilebilirlik denetimi yapılmadı.

**Hüküm:** Mevcut mimari geliştirilebilir; önce 1–11 numaralı veri güvenliği ve operasyon bulguları kapatılmalı. Ardından ana rapordaki servisler/dosyalar/ortak UI paketi uygulanmalı.

## Takip değişikliği — AdGuard entegrasyonunun kaldırılması

AdGuard menüsü, ağ sekmesi, istemcisi, 10 API operasyonu ve ilgili ayar/belgeler kaldırıldı. Kaldırılan özelliğin testleri yerine eski endpoint'lerin artık sunulmadığını ve Ethernet/Wi-Fi/Bluetooth ekranının DNS filtre isteği göndermeden çalıştığını doğrulayan regresyon kontrolleri kondu. Route inventory 194 route / 193 API operasyonu olarak güncellendi.

Son doğrulama: **354 API testi ve 55 UI testi geçti**; UI build, ESLint, module reachability, mevcut Ruff 0.15.0 ve diff whitespace kontrolü geçti. Agent kodu değişmediği için agent suite tekrar çalıştırılmadı. Pi'ye deploy, kurulu servis kaldırma veya DNS değişikliği yapılmadı. FCC Server adına mevcut kaynakta eşleşme bulunamadı; hangi servis/kurulumun kastedildiği netleşmeden sistemde kaldırma yapılmadı.

Geçici ortamın requirements tarafından kurulan Ruff 0.17.3 sürümü daha geniş varsayılan kurallarla hata veriyor. Aynı sürüm temiz HEAD arşivinde de kontrol edildi; bu kaldırmanın yol açtığı yeni bir lint başarısızlığı olarak raporlanmıyor. Komut: `python -m ruff check --output-format concise .`.

```text
Temiz HEAD: Found 1053 errors.
Bu değişiklikten sonra: Found 986 errors.
Örnek: config.py:1:1: EXE002 The file is executable but no shebang is present
```

Ruff sürümünü ve etkin kural kümesini CI/yerel geliştirme arasında sabitleme ihtiyacı sürüyor; bu kaldırma kapsamında formatter/lint politikası değiştirilmedi.
