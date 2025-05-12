from django.db import models
from users.models import User
from papers.models import Paper, AnonymizedPaper


def review_file_path(instance, filename):
    """Değerlendirme dosyası için dosya yolu oluşturur"""
    ext = filename.split('.')[-1]
    filename = f"{instance.paper.tracking_id}_reviewed.{ext}"
    return f"reviews/{filename}"


def combined_review_file_path(instance, filename):
    """Şifresi çözülmüş ve birleştirilmiş değerlendirme dosyası için dosya yolu oluşturur"""
    ext = filename.split('.')[-1]
    filename = f"{instance.paper.tracking_id}_combined_review.{ext}"
    return f"reviews/{filename}"


class Review(models.Model):
    STATUS_CHOICES = (
        ('assigned', 'Atandı'),
        ('in_progress', 'Değerlendiriliyor'),
        ('completed', 'Tamamlandı'),
        ('rejected', 'Reddedildi'),
    )
    
    RECOMMENDATION_CHOICES = (
        ('accept', 'Kabul'),
        ('minor_revision', 'Küçük Revizyon'),
        ('major_revision', 'Büyük Revizyon'),
        ('reject', 'Red'),
    )
    
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    review_file = models.FileField(upload_to=review_file_path, null=True, blank=True)
    combined_review_file = models.FileField(upload_to=combined_review_file_path, blank=True, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        reviewer_email = self.reviewer.email if self.reviewer else "N/A"
        return f"Review of {self.paper.tracking_id} by {reviewer_email}"


class Message(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='messages')
    sender_email = models.EmailField()
    is_editor = models.BooleanField(default=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message for {self.paper.tracking_id}"