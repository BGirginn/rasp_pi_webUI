# Günlük yönetim paketi — 2026-11-05

Çalışan kaynak başlangıcı: `f364db7`, GitHub etiketi `working-baseline-2026-11-05`. Bu etiket geliştirme öncesi durumu korur. Canlı Pi ile bu kaynağın kapsam farkları başlangıç notunda açıklanmıştır.

## Uygulanan davranış

- Oturum açıkken sayfa hash'i yenileme ve geçmiş gezinmesinde korunur; bilinmeyen sayfa Dashboard'a döner. Varsayılan vurgu sage; kayıtlı tema tercihi korunur.
- Services: aranabilir/sınıflandırılabilir servis tablosu, durum sayıları, log/bağımlılık ayrıntısı, açık stop onayı ve doğrulanmış işlem sonucu. Agent hatası örnek log ile örtülmez. CORE korunur; SYSTEM yalnız admin tarafından restart edilebilir.
- Files: kayıtlı kök seçimi, kökle sınırlı breadcrumbs, sıralama/arama/gizli dosyalar, dosya ayrıntısı, klasör oluşturma, upload/download ve açık copy/move/rename/delete formları. Admin mevcut izinli klasörü kaydedebilir; operator dosyaları yönetebilir; viewer erişemez. Backend rol ve kök denetimi yetkilidir.
- Upload ve copy mevcut hedefi ezmez; yarım yazım hata halinde temizlenir. Mutasyonlar no-follow directory FD kullanır; recursive copy link ve özel dosyaları reddeder. Move/rename işletim sisteminin atomik no-replace işlemini kullanır.
- Büyük transferlerde sahte yüzde gösterilmez; upload dosya sayısını ve hataları bildirir. Servis logları ve dosya listelerinde eski isteğin geç sonucu yeni seçimi değiştiremez.

## Doğrulama ve sınırlar

Yerel: UI 71 test, API 377 test, agent 149 test geçti. ESLint, Ruff 0.17.3, modül erişilebilirliği ve production build geçti. API'de AnyIO deprecation uyarısı var. API SPA testleri UI build sonrasında, aynı dist üzerinde eşzamanlı build yapılmadan çalıştırıldı.

Bağımsız incelemedeki üç Important bulgu için önce başarısız olan 8 parametrik test ardından düzeltmeler çalıştırıldı: parent symlink yarışı, eşzamanlı move hedefi ve `systemd-systemd-*` unit adları. Testler izole geçici dizinlerde çalışır.

Pi'ye bu paket kurulmadı. Yerel gerçek API ile tarayıcı giriş denemesi yapıldı, fakat başarılı giriş ve yenilenen sayfaların görsel/kullanım kabulü tamamlanamadı: Chrome otomasyon binary'si yok; native Brave test penceresi kayboldu ve tarayıcı başka kullanıcı etkileşimine geçti. Görsel kabul veya canlı Pi dosya/servis kabulü yapılmış sayılmaz. Linux/arm64 no-replace yolu ayrıca Pi'de denenmelidir.

Sınırlar:

- Dosya sistemleri arasında move açık hata döndürür; önce copy, ardından kullanıcı tarafından doğrulanmış delete gerekir. Copy dosya sahibi, ACL/xattr veya kaynak izinlerini koruyan bir yedekleme değildir; yeni dosyalar 0600, klasörler 0700 oluşturulur.
- Upload/download henüz devam ettirilebilir transfer veya kalıcı job değildir; download tarayıcı belleğine alınır. Büyük NAS transferleri kapsam dışıdır.
- Login'e yönlendirilen oturumsuz bookmark hedefi kaybolur. Delete onayında başında/sonunda boşluk olan adlar eşleşmez. Bunlar incelemedeki iki Minor bulgudur.
- Klasör kaydı mevcut projects registry'sini kullanır; NAS paylaşımı veya app store eklenmedi. İkisi TODO olarak durur.

## CI

Başlangıç commit'inin CI çalışmasında Ruff varsayılan kural kümesi değişimi ve SARIF yükleme hatası görüldü. Mevcut `E4/E7/E9/F` politikası açıkça yazıldı; mevcut ignore listesi korundu. SARIF action v4 ve yalnız security job'una `security-events: write` eklendi.

Kaynaklar: [Ruff breaking changes](https://github.com/astral-sh/ruff/blob/main/BREAKING_CHANGES.md), [GitHub SARIF yükleme belgesi](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file).
