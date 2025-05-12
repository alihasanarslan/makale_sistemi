# Akademik Makale Değerlendirme Sistemi

Bu proje, akademik makalelerin yüklenmesi, anonimleştirilmesi, değerlendirilmesi ve süreç takibinin yapılabilmesi için geliştirilmiş bir web tabanlı sistemdir.

## Özellikler

- **Makale Yükleme:** Kullanıcılar makalelerini sisteme yükleyebilir.
- **Anonimleştirme:** Yüklenen makalelerden yazar ve kurum bilgileri otomatik olarak gizlenir.
- **Hakem Atama ve Değerlendirme:** Editörler makaleleri hakemlere atayabilir, hakemler ise değerlendirme yapabilir.
- **Durum Takibi:** Kullanıcılar, makalelerinin değerlendirme ve işlem geçmişini takip edebilir.
- **PDF İşlemleri:** Makaleler üzerinde PDF anonimleştirme, görsel bulanıklaştırma ve değerlendirme raporlarının PDF’e eklenmesi gibi işlemler yapılır.

## Kurulum

1. Gerekli bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```
2. Veritabanı migrasyonlarını çalıştırın:
   ```
   python manage.py migrate
   ```
3. Geliştirme sunucusunu başlatın:
   ```
   python manage.py runserver
   ```

## Kullanılan Teknolojiler

- Python & Django
- Django Rest Framework
- PyMuPDF, Pillow, OpenCV (PDF ve görsel işlemleri için)
- NLTK, spaCy (Doğal dil işleme için)
- SQLite (varsayılan veritabanı)

## Klasörler

- `core/` : Ana uygulama ve genel ayarlar
- `papers/` : Makale işlemleri ve PDF servisleri
- `reviews/` : Değerlendirme ve hakem işlemleri
- `users/` : Kullanıcı yönetimi

## Notlar

- Proje geliştirme modunda çalışmaktadır. Gerçek ortamda kullanmadan önce güvenlik ve yapılandırma ayarlarını gözden geçirin.
- E-posta işlemleri konsola yönlendirilmiştir.

---

Daha ayrıntılı bir dokümantasyon veya özel bir bölüm istersen belirtmen yeterli!
