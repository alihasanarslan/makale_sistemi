import uuid
from django.db import models
from django.utils import timezone
import json


def paper_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.tracking_id}.{ext}"
    return f"papers/original/{filename}"


def anonymized_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.paper.tracking_id}_anonymized.{ext}"
    return f"papers/anonymized/{filename}"


def restored_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.paper.tracking_id}_restored.{ext}"
    return f"papers/restored/{filename}"


class Paper(models.Model):
    STATUS_CHOICES = (
        ('submitted', 'Yüklendi'),
        ('processing', 'İşleniyor'),
        ('reviewing', 'Değerlendiriliyor'),
        ('reviewed', 'Değerlendirildi'),
        ('revision', 'Revizyon'),
        ('accepted', 'Kabul Edildi'),
        ('rejected', 'Reddedildi'),
    )
    
    FIELD_CHOICES = (
        ('', 'Not Selected'),
        ('computer_science', 'Computer Science'),
        ('medicine', 'Medicine'),
        ('engineering', 'Engineering'),
        ('economics', 'Economics'),
        ('social_sciences', 'Social Sciences'),
        ('natural_sciences', 'Natural Sciences'),
        ('humanities', 'Humanities'),
        ('education', 'Education'),
        ('arts', 'Arts'),
        ('other', 'Other'),
    )

    tracking_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField()
    title = models.CharField(max_length=255, blank=True)
    original_file = models.FileField(upload_to=paper_file_path)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    keywords = models.TextField(blank=True)
    field = models.CharField(max_length=50, choices=FIELD_CHOICES, default='', blank=True, help_text="Makalenin ait olduğu akademik alan")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    detected_authors = models.TextField(blank=True, help_text="Tespit edilen yazarlar (JSON formatında)")
    detected_institutions = models.TextField(blank=True, help_text="Tespit edilen kurumlar (JSON formatında)")

    def get_detected_authors(self):

        if self.detected_authors:
            return json.loads(self.detected_authors)
        return []

    def set_detected_authors(self, authors_list):

        self.detected_authors = json.dumps(authors_list)

    def get_detected_institutions(self):

        if self.detected_institutions:
            return json.loads(self.detected_institutions)
        return []

    def set_detected_institutions(self, institutions_list):

        self.detected_institutions = json.dumps(institutions_list)

    def __str__(self):
        return f"Paper {self.tracking_id}"


class AnonymizedPaper(models.Model):
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='anonymized')
    file = models.FileField(upload_to=anonymized_file_path)
    anonymized_at = models.DateTimeField(auto_now_add=True)
    encryption_key = models.CharField(max_length=255, blank=True, null=True, help_text="Şifreleme için kullanilan anahtar")
    encryption_method = models.CharField(max_length=20, default="AES", help_text="Kullanilan şifreleme yöntemi")

    def __str__(self):
        return f"Anonymized {self.paper.tracking_id}"


class AnonymizedContent(models.Model):
    anonymized_paper = models.ForeignKey(AnonymizedPaper, on_delete=models.CASCADE, related_name='anonymized_contents')
    replacement_text = models.CharField(max_length=50, help_text="PDF'de görünen anonimleştirilmiş metin")
    original_text = models.CharField(max_length=255, help_text="Orijinal metin")
    encrypted_text = models.TextField(help_text="Şifrelenmiş orijinal metin")
    content_type = models.CharField(max_length=20, choices=(('author', 'Yazar'), ('institution', 'Kurum')), default='author')
    page_number = models.IntegerField(help_text="İçeriğin bulunduğu sayfa numarasi")
    position_data = models.TextField(blank=True, null=True, help_text="İçeriğin PDF'teki konumu (JSON)")

    def get_position(self):
        if self.position_data:
            return json.loads(self.position_data)
        return None

    def set_position(self, position_dict):
        self.position_data = json.dumps(position_dict)

    def __str__(self):
        return f"{self.content_type} - {self.replacement_text}"


class RestoredPaper(models.Model):
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='restored')
    anonymized_paper = models.OneToOneField(AnonymizedPaper, on_delete=models.CASCADE, related_name='restored')
    file = models.FileField(upload_to=restored_file_path)
    restored_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Restored {self.paper.tracking_id}"


class PaperLog(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.paper.tracking_id} - {self.action}"