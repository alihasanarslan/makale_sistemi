import os
import re
import tempfile
import uuid
import nltk
import fitz  
import spacy
from django.conf import settings
import time
from .encryption_service import EncryptionService


try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

try:
    nlp = spacy.load("en_core_web_trf")
except OSError:
    print("Spacy 'en_core_web_trf' dil modeli indiriliyor...")
    os.system("python -m spacy download en_core_web_trf")
    nlp = spacy.load("en_core_web_trf")


class PDFAnonymizer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = fitz.open(file_path)
        self.text_content = self._extract_text()
        self.redaction_list = []
        self.first_page_count = min(3, len(self.doc))
        self.reference_section_page = None

        self.tracking_id = os.path.basename(file_path).split('.')[0]

        self.encryption_service = EncryptionService()

        self.anonymized_content = []

        self.image_blur_list = []

    def _extract_text(self):
        text = ""
        for page in self.doc:
            text += page.get_text("text") + "\n"
        return text

    def _is_reference_section(self, text):


        reference_patterns = [
            r'^\s*References\s*$',
            r'^\s*REFERENCES\s*$',
            r'^\s*Bibliography\s*$',
            r'^\s*BIBLIOGRAPHY\s*$',
            r'^\s*Reference\s*$',
            r'^\s*REFERENCE\s*$',
            r'^\s*Works Cited\s*$',
            r'^\s*WORKS CITED\s*$',
            r'^\s*Kaynaklar\s*$',
            r'^\s*KAYNAKLAR\s*$',
            r'^\s*Kaynakça\s*$',
            r'^\s*KAYNAKÇA\s*$'
        ]

        section_header_pattern_strict = r'^\s*(?:[IVXLCDM]+\.?\s*)?REFERENCES\s*$' 

        lines = text.split('\n')

        for line_num, line in enumerate(lines):
            cleaned_line = line.strip()

            for pattern in reference_patterns:
                if re.fullmatch(pattern, cleaned_line):
                    print(f"LOG (_is_reference_section): SUCCESS - Explicit header match found: '{cleaned_line}' with pattern '{pattern}'")
                    return True

            if re.fullmatch(section_header_pattern_strict, cleaned_line.upper()):
                 print(f"LOG (_is_reference_section): SUCCESS - Strict Section header match found: '{cleaned_line}' with pattern '{section_header_pattern_strict}'")
                 return True


        return False

    def find_reference_section(self):

        for page_num in range(len(self.doc)):
            page_text = self.doc[page_num].get_text("text")
            if self._is_reference_section(page_text):
                self.reference_section_page = page_num
                print(f"Referans bölümü tespit edildi: Sayfa {page_num + 1}")
                return page_num


        print("Referans bölümü tespit edilemedi.")
        return None

    def detect_authors(self):

        author_patterns = [
            # Genel yazar formatları
            r'(?:Author[s]?:?|By)\\s*([A-Z][a-z]+(?:\\s[A-Z][a-z]+){1,3})',
            r'([A-Z][a-z]+\\s[A-Z][a-z]+),\\s*(?:and|&)\\s*([A-Z][a-z]+\\s[A-Z][a-z]+)',
            r'([A-Z][a-z]+\\s[A-Z][a-z]+)\\s*(?:and|&)\\s*([A-Z][a-z]+\\s[A-Z][a-z]+)',
            r'([A-Z][a-z]+\\s[A-Z][a-z]+),\\s*([A-Z][a-z]+\\s[A-Z][a-z]+)',
            # Email ile birlikte yazarlar
            r'([A-Z][a-z]+\\s[A-Z][a-z]+),\\s*[\\w\\.]+@[\\w\\.]+',
            # Akademik ünvanlarla birlikte yazarlar
            r'([A-Z][a-z]+\\s(?:[A-Z]\\.\\s?)?[A-Z][a-z\\-]+)\\s*\\([^)]*\\)',
            # Büyük harfle yazılmış yazarlar
            r'([A-Z][A-Z\\s]+)\\s*,\\s*([A-Z][A-Z\\s]+)',
            r'([A-Z][A-Z\\s]+)\\s+AND\\s+([A-Z][A-Z\\s]+)',
            # Tek satırda tüm yazarlar
            r'([A-Z][a-z]+\\s[A-Z][a-z]+),\\s*([A-Z][a-z]+\\s[A-Z][a-z]+),\\s*(?:and|&)\\s*([A-Z][a-z]+\\s[A-Z][a-z]+)',
            r'(?:Dr\\.|Prof\\.|Associate Prof\\.|Assistant Prof\\.)\\s+([A-Z][a-z]+(?:\\s+[A-Z][a-z\\.\\-]+){1,3})', # Unvanlar
            r'([A-Z][a-z]+\\s[A-Z]\\.\\s[A-Z][a-z]+(?:-[A-Z][a-z]+)?)', # Orta isim baş harfi ve tireli soyadı
            r'([A-Z][a-z]+\\s(?:van|von|de|La|Le)\\s[A-Z][a-z]+)', # Soyadı ekleri (van, de vb.)
            r'(?:\\d+\\.|\\([a-z]\\))\\s+([A-Z][a-z]+(?:\\s+[A-Z][a-z\\.\\-]+){1,3})', # Sıralama/Numaralandırma
            r'([A-Z][a-z]+(?:\\s+[A-Z][a-z\\.\\-]+){1,3})(?:\\*|†|\\d)?', # Dipnot işaretleri (isimden sonra)
        ]


        text_to_analyze = ""
        for i in range(self.first_page_count):
            text_to_analyze += self.doc[i].get_text("text") + "\n"


        authors = []
        doc = nlp(text_to_analyze[:5000])
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                authors.append(ent.text)


        for pattern in author_patterns:
            matches = re.findall(pattern, text_to_analyze)
            if matches:
                if isinstance(matches[0], tuple):

                    for match_group in matches:
                        authors.extend([name for name in match_group if name])
                else:

                    authors.extend(matches)


        filtered_authors = []
        for author in authors:

            author = author.strip()
            author = re.sub(r'[,.;:]$', '', author)
            words = author.split()


            is_valid_author = False
            if len(words) >= 2:

                if all(word[0].isupper() for word in words if word):

                    is_valid_author = True # Şimdilik sadece kelime kontrolü yeterli
            elif len(words) == 1 and len(author) > 1: # Tek harflik isimleri atla
                doc = nlp(author)
                if any(ent.label_ == "PERSON" for ent in doc.ents):

                    is_valid_author = True
            
            # Geçerli yazarları listeye ekleme
            if is_valid_author:
                 filtered_authors.append(author)

        # Tekrarlı yazarları sil
        unique_authors = list(set(filtered_authors))

        return unique_authors

    def detect_institutions(self):

        institution_patterns = [
            # Üniversiteler
            r'University of ([A-Z][a-zA-Z\\s,]+)', # Virgül içerebilen şehir/eyalet isimleri
            r'([A-Z][a-zA-Z\\s,]+) University',
            # Enstitüler
            r'([A-Z][a-zA-Z\\s,]+) Institute of ([A-Z][a-zA-Z\\s]+)',
            r'Institute of ([A-Z][a-zA-Z\\s,]+)',
            r'Indian Institute of ([A-Z][a-zA-Z\\s]+)',
            # Fakülteler ve Bölümler
            r'Faculty of ([A-Z][a-zA-Z\\s]+)',
            r'School of ([A-Z][a-zA-Z\\s]+)',
            r'Department of ([A-Z][a-zA-Z\\s]+(?:\\s*at\\s*[A-Z][a-zA-Z\\s]+)?)', # "Department of X at Y University"
            r'([A-Z][a-zA-Z\\s]+) College',
            r'([A-Z][a-zA-Z\\s]+) School',
            # Araştırma Merkezleri
            r'([A-Z][a-zA-Z\\s,]+) Research (?:Center|Centre|Laboratory|Lab|Institute)',
            r'([A-Z][a-zA-Z\\s,]+) (?:Science|Technology|Engineering) (?:Center|Centre|Laboratory|Lab|Institute)',
            # Şirketler ve Organizasyonlar
            r'([A-Z][a-zA-Z\\s,]+) (?:Corporation|Inc\\.|LLC|Ltd\\.|Foundation|Association|Hospital|Clinic|Bureau|National|International)',
            # Devlet Kurumları
            r'Ministry of ([A-Z][a-zA-Z\\s]+)',
            r'Department of ([A-Z][a-zA-Z\\s]+)',
            r'Government of ([A-Z][a-zA-Z\\s]+)',
            r'(?:Agency|Bureau) of ([A-Z][a-zA-Z\\s]+)',
            # YENİ EKLENEN KURUM DESENLERİ
            r'(?:Université|Universität|Universidad|Instituto|Faculdade)\\s+(?:de|di|of)?\\s?([A-Z][a-zA-Z\\s,]+)', # Uluslararası formatlar
            r'([A-Z][a-zA-Z\\s]+) Polytechnic Institute',
            r'National Institutes? of ([A-Z][a-zA-Z\\s]+)',
        ]


        text_to_analyze = ""
        for i in range(self.first_page_count):
            text_to_analyze += self.doc[i].get_text("text") + "\n"


        institutions = []
        doc = nlp(text_to_analyze[:5000])
        for ent in doc.ents:
            if ent.label_ == "ORG":

                if len(ent.text) > 7:
                    institutions.append(ent.text)


        exact_institution_names = [
            "Indian Institute of Information Technology Allahabad",
            "Ministry of Education, Government of India",
            "the Ministry of Education, Government of India"
        ]


        for inst in exact_institution_names:
            if inst in text_to_analyze:
                institutions.append(inst)


        for pattern in institution_patterns:
            try:
                matches = re.findall(pattern, text_to_analyze)
                if matches:
                    if isinstance(matches[0], tuple):

                        for match_group in matches:

                            if len(match_group) == 2:
                                full_institution = f"{match_group[0]} {match_group[1]}"
                                institutions.append(full_institution)
                            else:

                                for part in match_group:
                                    if part and len(part) > 5:
                                        institutions.append(part)
                    else:

                        for match in matches:
                            if match and len(match) > 5:
                                pattern_parts = pattern.split('(')[0]
                                pattern_suffix = pattern.split(')')[1] if ')' in pattern else ""


                                if "(" in pattern and ")" in pattern:
                                    full_institution = f"{pattern_parts}{match}{pattern_suffix}".strip()
                                    institutions.append(full_institution)
                                else:
                                    institutions.append(match)
            except Exception as e:
                print(f"Desen ile eşleşme hatası '{pattern}': {e}")


        filtered_institutions = []
        for institution in institutions:

            institution = institution.strip()
            institution = re.sub(r'[,.;:]$', '', institution)

            # Yeterince uzun ve anlamlı görünen kurumları tut
            if len(institution) > 5:

                words = institution.split()
                if words and words[0][0].isupper():

                    if any(keyword in institution.lower() for keyword in [
                        "university", "institute", "college", "school", "department",
                        "faculty", "lab", "laboratory", "center", "centre", "research",
                        "corporation", "foundation", "ministry", "agency", "government",
                        "indian", "technology", "allahabad"
                    ]):
                        filtered_institutions.append(institution)


        unique_institutions = list(set(filtered_institutions))

        return unique_institutions

    def blur_images_after_references(self, blur_factor=5):

        try:
            # Önce referans bölümünü tespit et (eğer daha önce tespit edilmediyse)
            if self.reference_section_page is None:
                print("LOG (blur_images_after_references): Referans bölümü tespit ediliyor")
                self.find_reference_section()
                
            # Referans bölümü bulunamadıysa, işlem yapma
            if self.reference_section_page is None:
                print("LOG (blur_images_after_references): HATA: Referans bölümü tespit edilemediği için çıkılıyor.")
                return 0
                
            print(f"LOG (blur_images_after_references): Referans bölümü sayfa: {self.reference_section_page + 1}, toplam sayfa: {len(self.doc)}") # LOG
            
            blurred_count = 0
            page_count = len(self.doc)
            

            start_page_for_blur = self.reference_section_page + 1
            print(f"LOG (blur_images_after_references): İşlenecek sayfa aralığı: range({start_page_for_blur}, {page_count})") # LOG
            for page_num in range(start_page_for_blur, page_count):
                page = self.doc[page_num]
                print(f"LOG (blur_images_after_references): Sayfa {page_num + 1} görsel işleniyor...") # LOG
                
                # Sayfadaki görüntüleri al
                try:
                    image_list = page.get_images(full=True)
                    print(f"LOG (blur_images_after_references): Sayfa {page_num + 1}'de {len(image_list)} görsel bulundu.") # LOG
                except Exception as e:
                    print(f"LOG (blur_images_after_references): Görsel listesi alınırken hata (Sayfa {page_num + 1}): {e}") # LOG
                    continue
                
                if not image_list:
                    print(f"LOG (blur_images_after_references): Sayfa {page_num + 1}'de işlenecek görsel yok.") # LOG
                    continue

                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        print(f"LOG (blur_images_after_references): Görsel işleniyor: xref={xref}")
                        

                        img_dict = self.doc.extract_image(xref)
                        

                        if not img_dict:
                            print(f"LOG (blur_images_after_references): xref={xref} için görüntü verisi çıkarılamadı.") # LOG
                            continue
                        

                        try:
                            from PIL import Image, ImageFilter
                            import io
                        except ImportError as e:
                            print(f"PIL kütüphanesi içe aktarılırken hata: {e}")
                            return 0
                        
                        img_bytes = img_dict["image"]
                        img_ext = img_dict["ext"]
                        print(f"LOG (blur_images_after_references): Görsel formatı: {img_ext}, boyutu: {len(img_bytes)} byte")
                        

                        if img_dict["smask"] > 0:
                            try:
                                print(f"LOG (blur_images_after_references): Görsel maskesi işleniyor: smask={img_dict['smask']}")
                                pix1 = fitz.Pixmap(img_bytes)
                                mask = fitz.Pixmap(self.doc.extract_image(img_dict["smask"])["image"])
                                pix = fitz.Pixmap(pix1, mask)
                                img_bytes = pix.tobytes()

                            except Exception as e:
                                print(f"LOG (blur_images_after_references): Maske işlenirken hata: {e}")
                                continue
                        

                        try:
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            print(f"LOG (blur_images_after_references): Görsel boyutları: {pil_img.size}, modu: {pil_img.mode}")
                        except Exception as e:
                            print(f"LOG (blur_images_after_references): Hata: Görüntü açılamadı - {e}")
                            continue
                        

                        try:
                            print(f"LOG (blur_images_after_references): Görsel bulanıklaştırılıyor, faktör: {blur_factor}")

                            blur_factor_float = float(blur_factor)
                            blurred_img = pil_img.filter(ImageFilter.GaussianBlur(blur_factor_float))
                        except Exception as e:
                            print(f"LOG (blur_images_after_references): Bulanıklaştırma hatası: {e}")
                            continue
                        

                        try:
                            output_bytes = io.BytesIO()

                            img_format = img_ext.upper()
                            if img_format == "JPG":
                                img_format = "JPEG"
                            elif img_format == "TIF":
                                img_format = "TIFF"

                            supported_formats = ["JPEG", "PNG", "GIF", "TIFF", "BMP"]
                            if img_format not in supported_formats:
                                print(f"LOG (blur_images_after_references): Uyarı: Desteklenmeyen format '{img_format}', PNG olarak kaydedilecek.")
                                img_format = "PNG"
                                

                            if pil_img.mode == 'P':
                                pil_img = pil_img.convert('RGBA' if img_format == 'PNG' else 'RGB')
                            elif pil_img.mode == 'LA':
                                pil_img = pil_img.convert('RGBA' if img_format == 'PNG' else 'RGB')

                            blurred_img.save(output_bytes, format=img_format)
                            output_bytes.seek(0)
                            print(f"LOG (blur_images_after_references): Bulanık görsel kaydedildi, format: {img_format}")
                        except Exception as e:
                            print(f"LOG (blur_images_after_references): Görüntü kaydedilirken hata: {e}")
                            continue
                        

                        try:

                            img_bbox = page.get_image_bbox(img)
                            if img_bbox.is_empty or img_bbox.is_infinite:
                                print(f"LOG (blur_images_after_references): Uyarı: xref={xref} için geçersiz veya boş bbox, atlanıyor.") # LOG
                                continue
                            rect = img_bbox
                            print(f"LOG (blur_images_after_references): Görsel konumu tespit edildi: {rect}")
                        except Exception as e:
                            print(f"LOG (blur_images_after_references): Görsel konumu tespit edilirken hata: {e}")
                            continue
                        

                        self.image_blur_list.append({
                            "page": page_num,
                            "rect": rect, 
                            "image_bytes": output_bytes.getvalue(),
                            "xref": xref
                        })
                        
                        blurred_count += 1
                        print(f"LOG (blur_images_after_references): Görsel {img_index+1} başarıyla bulanıklaştırıldı.")
                        
                    except Exception as e:
                        print(f"LOG (blur_images_after_references): Görüntü {img_index+1} işlenirken beklenmeyen hata: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
            

            if blurred_count > 0:
                print(f"LOG (blur_images_after_references): Toplam {blurred_count} görsel bulanıklaştırıldı.")
            else:
                print("LOG (blur_images_after_references): Bulanıklaştırılacak görsel bulunamadı.")
                
            return blurred_count
        except Exception as e:
            print(f"LOG (blur_images_after_references): Bulanıklaştırma işleminde genel beklenmeyen hata: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _apply_blurred_images(self):

        print(f"--- _apply_blurred_images başladı. Uygulanacak {len(self.image_blur_list)} görsel var. ---") # LOG
        try:
            for item in self.image_blur_list:
                try:
                    page = self.doc[item["page"]]
                    print(f"LOG (_apply_blurred_images): Sayfa {item['page'] + 1}, xref {item['xref']} için görsel uygulanıyor...") # LOG

                    page.draw_rect(item["rect"], color=(1, 1, 1), fill=(1, 1, 1))

                    page.insert_image(item["rect"], stream=item["image_bytes"])
                    print(f"LOG (_apply_blurred_images): Sayfa {item['page'] + 1}'deki görsel başarıyla yerleştirildi.") # LOG
                except Exception as e:
                    print(f"LOG ERROR (_apply_blurred_images): Görsel yerleştirme hatası (sayfa {item['page'] + 1}, xref: {item['xref']}, rect: {item['rect']}): {e}") # LOG
                    continue
            
            if self.image_blur_list:
                print(f"LOG (_apply_blurred_images): {len(self.image_blur_list)} bulanıklaştırılmış görsel uygulandı.") # LOG
        except Exception as e:
            print(f"LOG ERROR (_apply_blurred_images): Bulanıklaştırılmış görselleri uygulamada genel hata: {e}") # LOG
            import traceback
            traceback.print_exc()
        print("--- _apply_blurred_images bitti. ---") # LOG

    def anonymize_pdf(self, authors_to_anonymize=None, institutions_to_anonymize=None, output_dir=None, blur_images=True, blur_factor=5):

        print("--- anonymize_pdf başladı ---") # LOG

        self.find_reference_section()
        print(f"LOG: find_reference_section sonrası self.reference_section_page = {self.reference_section_page}") # LOG


        try:
            if blur_images:
                if self.reference_section_page is not None:
                    print(f"LOG: blur_images_after_references çağrılıyor (faktör={blur_factor})...") # LOG
                    blurred_count = self.blur_images_after_references(blur_factor=blur_factor)
                    print(f"LOG: blur_images_after_references döndü. Bulanıklaştırılan görsel sayısı: {blurred_count}") # LOG
                else:
                    print("LOG: Referans bölümü bulunamadığı için (self.reference_section_page is None) görsel bulanıklaştırma atlandı.") # LOG
            else:
                 print("LOG: blur_images=False olduğu için görsel bulanıklaştırma atlandı.") # LOG
        except Exception as e:
            print(f"GÖRSEL BULANIKLAŞTIRMA SIRASINDA HATA OLUŞTU (işlem devam ediyor): {e}")
            import traceback
            traceback.print_exc()


        if authors_to_anonymize is None:
            authors_to_anonymize = self.detect_authors()
        
        if institutions_to_anonymize is None:
            institutions_to_anonymize = self.detect_institutions()


        if output_dir is None:
            output_dir = os.path.dirname(self.file_path)
        
        os.makedirs(os.path.join(settings.MEDIA_ROOT, "papers/anonymized"), exist_ok=True)

        output_path = os.path.join(settings.MEDIA_ROOT, f"papers/anonymized/{self.tracking_id}_anonymized.pdf")


        encryption_key = self.encryption_service.generate_key()
        

        for page_num, page in enumerate(self.doc):

            if self.reference_section_page is not None and page_num == self.reference_section_page:
                print(f"Sayfa {page_num + 1} referans bölümü olduğundan atlanıyor...")
                continue

            print(f"Sayfa {page_num + 1} işleniyor...")


            page_text = page.get_text("text")


            for idx, author in enumerate(authors_to_anonymize):

                pattern = r'\b' + re.escape(author) + r'\b'
                for match in re.finditer(pattern, page_text):

                    try:

                        rects = page.search_for(author, hit_max=100)
                    except TypeError:

                        rects = page.search_for(author)

                    for rect in rects:

                        encrypted_text = self.encryption_service.encrypt(author)
                        

                        anonymized_item = {
                            "page": page_num,
                            "rect": rect,
                            "replacement_text": f"[AUTHOR{idx+1}]",
                            "original_text": author,
                            "encrypted_text": encrypted_text,
                            "content_type": "author"
                        }
                        

                        self.redaction_list.append({
                            "page": page_num,
                            "rect": rect,
                            "text": f"[AUTHOR{idx+1}]", 
                            "replace_text": True
                        })
                        

                        self.anonymized_content.append(anonymized_item)


            if page_num < self.first_page_count or (self.reference_section_page is not None and page_num > self.reference_section_page):
                for idx, institution in enumerate(institutions_to_anonymize):
                    if len(institution) < 5:
                        continue


                    pattern = r'\b' + re.escape(institution) + r'\b'
                    for match in re.finditer(pattern, page_text):

                        try:

                            rects = page.search_for(institution, hit_max=100)
                        except TypeError:

                            rects = page.search_for(institution)

                        for rect in rects:

                            encrypted_text = self.encryption_service.encrypt(institution)
                            

                            anonymized_item = {
                                "page": page_num,
                                "rect": rect,
                                "replacement_text": f"[INSTITUTION{idx+1}]",
                                "original_text": institution,
                                "encrypted_text": encrypted_text,
                                "content_type": "institution"
                            }
                            

                            self.redaction_list.append({
                                "page": page_num,
                                "rect": rect,
                                "text": f"[INSTITUTION{idx+1}]",
                                "replace_text": True
                            })
                            

                            self.anonymized_content.append(anonymized_item)


        try:
            if blur_images and self.image_blur_list:
                print(f"LOG: _apply_blurred_images çağrılıyor. Liste boyutu: {len(self.image_blur_list)}") # LOG
                self._apply_blurred_images()
            elif blur_images:
                print("LOG: image_blur_list boş olduğu için _apply_blurred_images çağrılmadı.") # LOG
        except Exception as e:
            print(f"BULANIK GÖRSELLER UYGULANIRKEN HATA OLUŞTU (işlem devam ediyor): {e}")
            import traceback
            traceback.print_exc()


        print(f"\nAnonimleştirme işlemleri uygulanıyor... ({len(self.redaction_list)} adet redaksiyon)")


        for item in self.redaction_list:
            page = self.doc[item["page"]]
            try:

                if item["replace_text"] and item["text"]:

                    annot = page.add_redact_annot(item["rect"], text=item["text"], fontname="helv", fontsize=11)
                else:

                    annot = page.add_redact_annot(item["rect"], fill=(1, 1, 1))
            except TypeError as e:

                print(f"Uyarı: Text parametresi kullanılamıyor, sadece redaksiyon uygulanacak: {e}")
                annot = page.add_redact_annot(item["rect"], fill=(1, 1, 1))


        for page in self.doc:
            try:
                page.apply_redactions()
            except Exception as e:
                print(f"Redaksiyon uygulama hatası: {e}")


        try:
            self.doc.save(output_path)
            print(f"Anonimleştirilmiş PDF kaydedildi: {output_path}")
            return output_path, encryption_key, self.anonymized_content
        except Exception as e:
            print(f"PDF kaydetme hatası: {e}")
            return None, None, None
        finally:
            self.doc.close()

    @staticmethod
    def restore_original_pdf(anonymized_pdf_path, encrypted_content_data, encryption_key):

        encryption_service = EncryptionService()
        encryption_service.load_key(encryption_key)
        

        doc = fitz.open(anonymized_pdf_path)
        

        tracking_id = os.path.basename(anonymized_pdf_path).split('_')[0]
        

        for content in encrypted_content_data:

            original_text = encryption_service.decrypt(content["encrypted_text"])
            page_num = content["page"]
            replacement_text = content["replacement_text"]
            

            page = doc[page_num]
            

            try:

                rects = page.search_for(replacement_text, hit_max=100)
                
                for rect in rects:
                    page.add_redact_annot(rect, text=original_text, fontname="helv", fontsize=11)
            except Exception as e:
                print(f"Metin değiştirme hatası: {e}")
        

        for page in doc:
            try:
                page.apply_redactions()
            except Exception as e:
                print(f"Redaksiyon uygulama hatası: {e}")
        

        restored_path = os.path.join(settings.MEDIA_ROOT, f"papers/restored/{tracking_id}_restored.pdf")
        os.makedirs(os.path.dirname(restored_path), exist_ok=True)
        
        try:
            doc.save(restored_path)
            print(f"Orijinal haline döndürülmüş PDF kaydedildi: {restored_path}")
            return restored_path
        except Exception as e:
            print(f"PDF kaydetme hatası: {e}")
            return None
        finally:
            doc.close()

    @staticmethod
    def add_review_to_pdf(pdf_path, reviewer_comments, recommendation, tracking_id):

        print(f"Hakem değerlendirmesi PDF'e ekleniyor: {pdf_path}")

        doc = fitz.open(pdf_path)
        

        page = doc.new_page(width=595, height=842)  # A4 bıyutu
        

        page_num = doc.page_count - 1
        

        text = "HAKEM DEĞERLENDİRMESİ"
        page.insert_text((50, 50), text, fontsize=16, fontname="helv-b")
        

        text = f"Makale ID: {tracking_id}"
        page.insert_text((50, 80), text, fontsize=12, fontname="helv")
        

        text = f"Tavsiye: {recommendation.upper()}"
        page.insert_text((50, 110), text, fontsize=12, fontname="helv-b")
        

        from datetime import datetime
        text = f"Değerlendirme Tarihi: {datetime.now().strftime('%d.%m.%Y')}"
        page.insert_text((50, 140), text, fontsize=12, fontname="helv")
        

        text = "Hakem Yorumları:"
        page.insert_text((50, 180), text, fontsize=14, fontname="helv-b")
        

        max_width = 495
        max_lines_per_page = 30
        

        comments_lines = []
        words = reviewer_comments.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            #
            if len(test_line) * 5 < max_width:
                current_line = test_line
            else:
                comments_lines.append(current_line)
                current_line = word
                

        if current_line:
            comments_lines.append(current_line)
        

        y_pos = 210
        line_height = 20
        line_count = 0
        
        for line in comments_lines:

            if line_count >= max_lines_per_page:
                page = doc.new_page(width=595, height=842)
                page_num += 1
                y_pos = 50
                line_count = 0
            
            page.insert_text((50, y_pos), line, fontsize=12, fontname="helv")
            y_pos += line_height
            line_count += 1
        

        output_dir = os.path.dirname(pdf_path)
        output_path = os.path.join(settings.MEDIA_ROOT, f"reviews/{tracking_id}_reviewed.pdf")
        

        os.makedirs(os.path.join(settings.MEDIA_ROOT, "reviews"), exist_ok=True)
        
        try:
            doc.save(output_path)
            print(f"Değerlendirme eklenmiş PDF kaydedildi: {output_path}")
            return output_path
        except Exception as e:
            print(f"PDF kaydetme hatası: {e}")
            return None
        finally:
            doc.close()

    def has_blurrable_images(self):

        if self.reference_section_page is None:
            self.find_reference_section()
            

        if self.reference_section_page is None:
            return False
            
        page_count = len(self.doc)
        

        start_page_for_check = self.reference_section_page + 1
        for page_num in range(start_page_for_check, page_count):
            page = self.doc[page_num]
            
            try:

                image_list = page.get_images(full=True)
                

                if image_list and len(image_list) > 0:
                    return True
            except Exception:

                continue
        

        return False

def anonymized_file_path(instance, filename):

    import os
    print(f"Anonimleştirme dosyası oluşturuluyor. Filename: {filename}")
    try:
        tracking_id = instance.paper.tracking_id
        print(f"Tracking ID: {tracking_id}")
    except Exception as e:
        print(f"Tracking ID alınamadı: {e}")

        tracking_id = os.path.splitext(filename)[0]
    
    ext = filename.split('.')[-1]
    new_filename = f"{tracking_id}_anonymized.{ext}"
    print(f"Oluşturulan dosya adı: {new_filename}")
    
    return f"papers/anonymized/{new_filename}"