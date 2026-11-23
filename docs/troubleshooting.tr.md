# Sorun giderme ve gizlilik

[Ana sayfa](../README.tr.md) · [English](troubleshooting.md)

Entegrasyon internet ve Vestel/homevsmart bulutuna bağlıdır. Geliştiricinin bildirdiği dört fiziksel cihaz dışında model desteği doğrulanmış sayılmaz; model ve firmware bilgilerini içeren uyumluluk tablosu henüz yayımlanmamıştır.

| Belirti | Kontrol / çözüm |
| --- | --- |
| Bağlantı hatası, istek sınırı veya geçici sunucu sorunu | İnterneti ve resmî uygulamayı kontrol edin. Düzenli sorgunun yeniden denemesini bekleyin; art arda giriş denemeleri istek sınırını artırabilir. |
| Geçersiz hesap / yeniden giriş isteği | Hesabı resmî uygulamada doğrulayıp Home Assistant'ın yeniden giriş akışını tamamlayın. |
| Cihaz görünmüyor veya kullanılamıyor | Seçilen evi, desteklenen cihaz türünü, bağlantıyı ve paneldeki uzaktan kontrol iznini kontrol edin. Onarımlar bölümüne bakın. |
| Çalışırken bir seçenek kullanılamıyor | Program, aşama, mod veya uzaktan kontrol durumu değişikliği engelliyor olabilir. |
| Komut kabul edildi ancak doğrulanmadı | Yeniden denemeden önce cihazı ve resmî uygulamayı kontrol edin. Bu hataya otomatik tekrar döngüsü bağlamayın. |
| Tüketim sensörleri yok veya boş | İsteğe bağlı varlıkları varlık ayarlarından etkinleştirin ve arka plan sorgusunu bekleyin. Eksik tüketim verisi kontrol arızası anlamına gelmez. |

Hata bildiriminden önce uygulamadaki bağlantıyı ve panelin uzaktan kontrol iznini kontrol edin. Entegrasyon menüsünden maskelenmiş tanılama indirilebilir. Paylaşmadan önce dosyayı inceleyin; şifre, token, seri numarası veya MAC adresi paylaşmayın.

## Gizlilik ve güvenlik

Tanılama yalnızca seçilen teknik metadata alanlarını (model, firmware, cihaz türü ve bağlantı bilgileri), özellik tanımlarını, register durumlarını, uyumluluk sorunlarını ve komut doğrulama sonuçlarını içerir. Bilinmeyen metadata alanları alınmaz. Bilinen hassas alanlar ve başka metinlerde tekrarlanan değerler, iç içe veriler ve gömülü JSON dahil maskelenir. Yeni bulut alanları kişisel bilgi içerebileceğinden paylaşmadan önce dosyayı yine de inceleyin.

E-posta, parola ve refresh token Home Assistant'ın yapılandırma kaydında saklanır. Token yenilemesi reddedildiğinde giriş yapılabilmesi için parola tutulur; entegrasyona özel ek bir şifreleme katmanı yoktur. Yapılandırma dosyalarını ve yedekleri kimlik bilgisi içeriyor gibi koruyun. Tanılama, bilinen kimlik bilgilerini maskeleme için kullanır; yapılandırma kaydını dışarı aktarmaz.

Kimlik bilgileri bu depoya veya geliştiriciye gönderilmez; giriş işlemi bulut sağlayıcısına yapılır. Güvenlik açığı bildirim yöntemi için [SECURITY.md](../SECURITY.md) dosyasına bakın. Hassas bilgi içermeyen normal hatalar [Issues](https://github.com/halilyildiz/vestel-akilli-yasam/issues) bölümünden bildirilebilir.

## Kaldırma

Önce Ayarlar → Cihazlar ve hizmetler bölümünden entegrasyon kaydını kaldırın. Ardından HACS/Marketplace üzerinden paketi kaldırıp istenirse yeniden başlatın. Kaydın kaldırılması Home Assistant varlıklarını da kaldırır; bunlara bağlı otomasyonları güncellemeniz gerekir. Resmî uygulamadaki cihaz eşleştirmeleri ayrı tutulur.
