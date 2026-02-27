# Güvenlik Politikası

## Desteklenen Sürümler

Şu anda güvenlik güncellemeleri alan sürümler:

| Sürüm | Destekleniyor |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.0.x   | :x:                |

## Güvenlik Açığı Bildirimi

Güvenlik açığı bulduysanız, lütfen **herkese açık issue açmayın**.

Bunun yerine:

1. **E-posta gönderin:** security@example.com
2. Açığı detaylı açıklayın
3. Yeniden üretme adımlarını ekleyin
4. Olası etkiyi belirtin

## Güvenlik En İyi Uygulamaları

### Kullanıcılar İçin

1. **Güvenilir Kaynaklar:** Sadece güvendiğiniz kaynaklardan M3U listesi yükleyin
2. **SSL Doğrulama:** Mümkünse SSL doğrulamasını aktif tutun
3. **Yerel Kullanım:** Uygulamayı public internete açmayın
4. **Güncellemeler:** Düzenli olarak güncellemeleri kontrol edin
5. **Güçlü Şifreler:** Deployment'ta güçlü şifreler kullanın

### Geliştiriciler İçin

1. **Bağımlılıklar:** Düzenli olarak `pip list --outdated` çalıştırın
2. **Code Review:** Tüm PR'ları inceleyin
3. **Input Validation:** Kullanıcı girdilerini doğrulayın
4. **Error Handling:** Hassas bilgileri loglara yazmayın
5. **HTTPS:** Production'da HTTPS kullanın

## Bilinen Güvenlik Konuları

### SSL Sertifika Doğrulaması

Uygulama varsayılan olarak SSL sertifika doğrulamasını bypass eder. Bu, bazı IPTV sağlayıcılarının sertifika sorunları nedeniyle yapılmıştır.

**Risk:** Man-in-the-middle saldırılarına açık olabilir.

**Çözüm:** `utils/config.py` dosyasında `DISABLE_SSL_VERIFY = False` yapın.

### Kullanıcı Girdileri

M3U dosyaları ve URL'ler kullanıcıdan gelir ve potansiyel olarak zararlı içerik barındırabilir.

**Risk:** XSS, code injection

**Çözüm:** Tüm girdiler sanitize edilir, ancak dikkatli olun.

## Güvenlik Güncellemeleri

Güvenlik güncellemeleri [CHANGELOG.md](CHANGELOG.md) dosyasında `[SECURITY]` etiketi ile işaretlenir.

## Sorumluluk Reddi

Bu yazılım "olduğu gibi" sağlanır. Güvenlik garantisi verilmez. Kullanım riski size aittir.

## İletişim

Güvenlik soruları için: security@example.com
