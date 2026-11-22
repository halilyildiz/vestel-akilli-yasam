# Vestel Akıllı Yaşam — Home Assistant

Vestel Akıllı Yaşam uygulamasına eklenmiş cihazlar için **resmî olmayan** bulut entegrasyonu. Vestel tarafından geliştirilmez veya desteklenmez.

## Destek

Klima (**AC**), kurutmalı çamaşır makinesi (**WD**), bulaşık makinesi (**DW**) ve buzdolabı (**RF**) desteklenir. Kontroller cihazın servis tanımından oluşturulur. Aynı protokolü kullanmayan modeller, yalnız yıkama yapan makineler, ayrı kurutucular, fırınlar ve diğer ürün türleri için destek garantisi yoktur.

## Kurulum

Home Assistant 2026.11.0 veya sonrası ve uygulamada önceden eşleştirilmiş cihazlar gerekir.

1. Ayarlar → Marketplace → Özel depolar bölümünde aşağıdaki adresi **Integration** türünde ekleyin:
   `https://github.com/halilyildiz/vestel-akilli-yasam`
2. **Vestel Akıllı Yaşam** paketini yükleyin; istenirse yeniden başlatın.
3. Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → **Vestel Akıllı Yaşam**.
4. Uygulamadaki e-posta ve şifrenizle giriş yapıp evinizi seçin.

Genel katalog kabulü tamamlanmadan da özel depo bağlantısıyla kurulabilir. Eski klima entegrasyonu veya keşif eklentisi gerekmez. Bu entegrasyonun elle kurulmuş bir sürümünden geçerken mevcut kaydı kaldırmayın: `vestel_appliances` alan adı ve varlık kimlikleri korunur.

## Davranış

- Desteklenen yeni cihazlar, seçilen uygulama evine eklendikten sonraki başarılı sorguda bulunur; normal sorgu aralığı 45 saniyedir. Yeniden yükleme gerekmez.
- Canlı MQTT olayları buluttan güncel durum okunmasını tetikler; bağlantı kurulamazsa düzenli sorgulama devam eder.
- Firmware/model değişiminde özellik tanımı yenilenir. Uyumsuz bir tanım diğer cihazları durdurmaz; Ayarlar → Sistem → Onarımlar altında bildirilir.
- Teknik tanılama ve günlük/aylık tahmini tüketim sensörleri varsayılan olarak kapalıdır. Tahminler gerçek sayaç ölçümü değildir.
- Seçili program sensörleri, seçim kontrolü çalışma sırasında kullanılamaz olduğunda programı göstermeye devam eder.
- Çalıştırma işlemleri cihaz panelindeki uzaktan kontrol iznine ve geçerli program durumuna bağlıdır. Geciken komut onayı otomatik tekrar gönderimine neden olmaz.

## Sınırlar ve sorun bildirimi

Entegrasyon internet ve Vestel/homevsmart bulutuna bağlıdır. Mevcut dört fiziksel cihaz dışındaki modeller denenmiş sayılmaz. 103 çevrimdışı test, tüm Vestel modellerinin fiziksel doğrulaması değildir.

Hata bildiriminden önce uygulamadaki bağlantıyı ve panelin uzaktan kontrol iznini kontrol edin. Entegrasyon menüsünden maskelenmiş tanılama indirilebilir. Paylaşmadan önce dosyayı inceleyin; şifre, token, seri numarası veya MAC adresi paylaşmayın.

Tüketim, fatura servisleri, geliştirme ve kaldırma ayrıntıları için [İngilizce belgeye](README.md) bakın.
