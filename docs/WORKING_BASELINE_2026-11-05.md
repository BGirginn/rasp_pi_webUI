# Çalışan temel sürüm — 5 Kasım 2026

Arayüz ve işlev geliştirmelerine başlamadan önce alınan geri dönüş noktasıdır.
Git etiketi: `working-baseline-2026-11-05`.

Bu kaynak anlık görüntüsü terminal bağlantı döngüsü düzeltmesini, panelden AdGuard
entegrasyonunun kaldırılmasını, denetim raporlarını ve NAS/app store TODO maddelerini içerir.
Üretime hazır veya bütün özellikleri eksiksiz bir sürüm olarak değerlendirilmemelidir.
Bilinen sınırlamalar [teknik denetimde](TECHNICAL_AUDIT_2026-11-05.md) kayıtlıdır.

## Doğrulama

- UI: 61 test, ESLint, module reachability ve production build başarılı.
- API: gereksinim dosyasıyla kurulmuş geçici ortamda 354 test başarılı.
- Agent: 149 test başarılı.
- Kontrol ortamı macOS arm64; Python 3.14.10 ve Node 26.13.0.
- UI build tamamlandıktan sonra API suite çalıştırılmalıdır; build'in `dist`
  klasörünü yenilemesi ile SPA testleri aynı anda çalıştırılmamalıdır.
- Canlı Pi'de terminal hotfix'i uygulanmış; Tailscale/Caddy üzerinden aynı WebSocket
  bağlantısında `whoami` ve 35 saniye sonra `uptime` başarıyla doğrulanmıştır.

## Kaynak ile canlı kurulumun ayrımı

Canlı Pi tabanı `b763edeb7198c1b711c6537aad6e0ec2887eaa06` ve terminal hotfix'idir.
Bu kaynak anlık görüntüsündeki AdGuard kaldırımı ve diğer belgeler Pi'ye ayrıca
dağıtılmamıştır. Sırf bu commit'in GitHub'a gönderilmesi Pi'yi güncellemez.
Terminal hotfix'inin kanıtları ve geri dönüş yolu [terminal belgesindedir](TERMINAL_CONNECTIONS.md).

Bu etiket değiştirilmeyecek; sonraki geliştirmeler ayrı commit'lerde ilerleyecek.
Etikete dönmek veritabanını veya kullanıcı dosyalarını geri almaz.
