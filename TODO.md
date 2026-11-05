# TODO

- [ ] Gelecekte NAS kullanımına yönelik düzenleme.
  - Disk/mount yönetimini dosya kökleri, paylaşımlar ve kullanıcı/grup izinleriyle ilişkilendir.
  - Disk bağlantısı kesilmesi, yeniden başlatma ve yedekten geri yükleme senaryolarını gerçek Pi üzerinde doğrula.
- [ ] Üçüncü taraf bir app store'u uçtan uca, tam çalışır şekilde entegre et.
  - Hedef Pi'nin OS/arm64 uyumluluğuna göre sağlayıcı seç; katalog, kurulum, başlatma/durdurma, güncelleme ve kaldırmayı panelden yönet.
  - Kalıcı uygulama verilerini, port çakışmalarını, yetkileri, işlem durumlarını ve hata/kurtarma akışlarını kapsa.
  - Yalnız bağlantı veya iframe eklemekle sınırlama; tüm yaşam döngüsünü gerçek Pi üzerinde kabul testleriyle doğrula.

- [ ] Google Drive backup entegrasyonunu yeni akista tekrar devreye almak.
  - Mevcut durum: gecici olarak devre disi.
  - Hedef: yeni auth/setup akisi ve daha guvenli cloud backup modeli.
