# Geliştirme ve çalışma davranışı

[Ana sayfa](../README.tr.md) · [English](development.md)

## Çalışma davranışı

- Desteklenen yeni cihazlar, seçilen uygulama evine eklendikten sonraki başarılı sorguda bulunur; normal sorgu aralığı 45 saniyedir. Yeniden yükleme gerekmez.
- Canlı MQTT olayları buluttan güncel durum okunmasını tetikler; bağlantı kurulamazsa düzenli sorgulama devam eder.
- Cihaz kontrolleri ve canlı güncellemeler enerji geçmişini beklemeden başlar. Tüketim bilgileri arka planda alınır; ilk sorgu, entegrasyon kaldırılırken veya yeniden yüklenirken iptal edilir.
- Firmware/model değişiminde özellik tanımı yenilenir. Uyumsuz bir tanım diğer cihazları durdurmaz; Ayarlar → Sistem → Onarımlar altında bildirilir.
- Teknik tanılama ve günlük/aylık tahmini tüketim sensörleri varsayılan olarak kapalıdır. Tahminler gerçek sayaç ölçümü değildir.
- Seçili program sensörleri, seçim kontrolü çalışma sırasında kullanılamaz olduğunda programı göstermeye devam eder.
- Çalıştırma işlemleri cihaz panelindeki uzaktan kontrol iznine ve geçerli program durumuna bağlıdır. Geciken komut onayı otomatik tekrar gönderimine neden olmaz.
- Paylaşılan register'larda yalnızca hedeflenen bit alanları ve otomatik kapatılan uyumsuz seçenekler doğrulanır. Aynı register'daki başka bir ayarın değişmesi onayı engellemez.
- Geçici kimlik sunucusu hataları ve istek sınırları bağlantı hatası olarak ele alınır. Bozuk yanıtlar kayıtlı oturum bilgileri değiştirilmeden reddedilir. Gerçek hesap/token reddinde yeniden giriş istenebilir.
- Hesaptan kaldırılan cihazların kayıtları otomatik silinmez; varlıklar kullanılamaz olarak tutulur.

## Doğrulama

```sh
python -m unittest discover -s tests -v
```

Çevrimdışı test kümesi protokol sınırları, oturum hataları, yanıt doğrulama, komut geri okuması, cihaz aileleri, yalnızca izlenen cihazlarda komut engelleme, arka plan başlangıcı, enerji hatalarının ayrılması ve tanılama maskelemesini denetler. Verilerde sentetik cihaz bilgileri kullanılır; gerçek cihaza veya buluta çağrı yapılmaz. Home Assistant sınıflarının çoğu taklittir; bu testler gerçek Home Assistant veya tüm fiziksel modellerin doğrulaması değildir. Yeni WM/FD kontrolleri ile TD/OV izleme kapsamı henüz yayımlanmamıştır; ayrıntılar [cihaz aileleri ve APK bulguları](device-families.md) belgesindedir.

GitHub Actions çevrimdışı testleri, hassfest ve HACS doğrulamasını çalıştırır. Kontrollerin geçmesi, HACS genel kataloğuna kabul edildiği anlamına gelmez.
