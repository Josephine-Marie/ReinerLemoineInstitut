from decimal import Decimal
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from polymorphic.query import PolymorphicQuerySet
from parler.managers import TranslatableManager, TranslatableQuerySet
from parler.models import TranslatableModelMixin, TranslatedFieldsModel, TranslatedFields
from parler.fields import TranslatedField
from cms.models.fields import PlaceholderField
from shop.money import Money, MoneyMaker
from shop.money.fields import MoneyField
from shop import deferred
from shop.models.product import BaseProduct, BaseProductManager, AvailableProductMixin, CMSPageReferenceMixin
from shop.models.defaults.cart import Cart
from shop.models.defaults.cart_item import CartItem
from shop.models.order import BaseOrderItem
from shop.models.defaults.delivery import Delivery
from shop.models.defaults.delivery_item import DeliveryItem
from shop.models.defaults.order import Order
from shop.models.defaults.mapping import ProductPage, ProductImage
from shop_sendcloud.models.address import BillingAddress, ShippingAddress
from shop.models.customer import BaseCustomer
from ssccms.related import BaseProductVideo, BaseCustomerImage, BaseProductSubtitles
from ssccms import settings
from filer_app.models import FilerVideo
from filer.models.filemodels import File
from filer.models.imagemodels import Image


__all__ = ['Cart', 'CartItem', 'Order', 'Delivery', 'DeliveryItem',
           'BillingAddress', 'ShippingAddress', 'Customer', ]


class CustomerImage(BaseCustomerImage):
    class Meta(BaseCustomerImage.Meta):
        abstract = False


class Customer(BaseCustomer):
    SALUTATION = [('mrs', _("Mrs.")), ('mr', _("Mr.")), ('na', _("(n/a)"))]

    salutation = models.CharField(
        _("Salutation"),
        max_length=5,
        choices=SALUTATION,
        null=True,
        blank=True
    )

    videocode = models.BigIntegerField(
        _("Videocode"),
        null=True,
        default=None,
        unique=True
    )

    birth_date = models.DateField(
        _("Date of birth"),
        null=True,
        blank=True
    )
    
    image = models.ManyToManyField(
        Image, 
        through=CustomerImage
    )
    
    newsletter_subscription = models.BooleanField(
        verbose_name=_('Subscribed to newsletter'),
        default=True
    )

    videoupload_notification = models.BooleanField(
        _('Subscribed to video upload notifications'),
        default=False
    )

    adult = models.BooleanField(
        _('Legal age confirmed'),
        default=False
    )

    coins = models.IntegerField(
        _('Account balance'),
        default=0
    )

    class Meta:
        verbose_name=_("Customer")
        verbose_name_plural=_("Customers")

    def get_number(self):
        return self.number

    def get_or_assign_number(self):
        if self.number is None:
            aggr = Customer.objects.filter(number__isnull=False).aggregate(models.Max('number'))
            self.number = (aggr['number__max'] or 0) + 1
            self.save()
        return self.get_number()

    def as_text(self):
        template_names = [
            '{}/customer.txt'.format(settings.APP_LABEL),
            'shop/customer.txt',
        ]
        template = select_template(template_names)
        return template.render({'customer': self})


class OrderItem(BaseOrderItem):
    quantity = models.PositiveIntegerField(_("Ordered quantity"))
    canceled = models.BooleanField(_("Item canceled "), default=False)

    def populate_from_cart_item(self, cart_item, request):
        super().populate_from_cart_item(cart_item, request)
        # the product's unit_price must be fetched from the product's variant
        try:
            variant = cart_item.product.get_product_variant(
                product_code=cart_item.product_code)
            self._unit_price = Decimal(variant.unit_price)
        except (KeyError, ObjectDoesNotExist) as e:
            raise CartItem.DoesNotExist(e)


class Catchphrase(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=50,
        unique=True,
    )

    class Meta:
        verbose_name = _('Catchword')
        verbose_name_plural = _('Catchphrases')

    def __str__(self):
        return self.name


class ProductQuerySet(TranslatableQuerySet, PolymorphicQuerySet):
    pass

class ProductManager(BaseProductManager, TranslatableManager):
    queryset_class = ProductQuerySet

    def get_queryset(self):
        qs = self.queryset_class(self.model, using=self._db)
        return qs.prefetch_related('translations')


# Materialize many-to-many relation with Django-Filer custom models from filer_app / ssccms.related
class ProductSubtitles(BaseProductSubtitles):
    class Meta(BaseProductSubtitles.Meta):
        abstract = False

class ProductVideo(BaseProductVideo):
    class Meta(BaseProductVideo.Meta):
        abstract = False


class Product(CMSPageReferenceMixin, TranslatableModelMixin, BaseProduct):
    product_name = models.CharField(
        _("Product Name"),
        max_length=255,
    )

    slug = models.SlugField(
        _("Slug"),
        unique=True,
    )

    unit_price = MoneyField(
        _("Unit price"),
        default=0,
        decimal_places=3,
        help_text=_("Net price for this product"),
    )

    quantity = models.PositiveIntegerField(
        _("Quantity"),
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Available quantity in stock")
    )

    videofile = models.ManyToManyField(
        FilerVideo, 
        through=ProductVideo,
        related_name='video'
    )

    subtitles = models.ManyToManyField(
        'filer.File',
        through=ProductSubtitles,
        related_name='subtitles'
    )

    caption = TranslatedField()

    # common product properties
    catchphrases = models.ManyToManyField(
        Catchphrase,
        verbose_name=_("Kategory")
    )

    # controlling the catalog
    order = models.PositiveIntegerField(
        _("Sort by"),
        db_index=True,
    )

    cms_pages = models.ManyToManyField(
        'cms.Page',
        through=ProductPage,
        help_text=_("Choose list view this product shall appear on."),
    )

    images = models.ManyToManyField(
        'filer.Image',
        through=ProductImage,
        related_name='img'
    )
    
    class Meta:
        ordering = ('order',)
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

    objects = ProductManager()

    # filter expression used to lookup for a product item using the Select2 widget
    lookup_fields = ['product_name__icontains']

    def __str__(self):
        return self.product_name

    def get_videofile_path(self):
        try:
            filename = File.objects.filter(id=(ProductVideo.objects.filter(product_id=self.id).values('video_id')[0]['video_id'])).values('original_filename')[0]['original_filename']
            name = filename[:filename.rfind('.')]
            return f"/media/filer_public_streams/{name}/{name}.m3u8"
        except:
            pass

    def get_subtitles_path(self):
        try:
            return File.objects.filter(id=(ProductSubtitles.objects.filter(product_id=self.id).values('subtitles_id')[0]['subtitles_id'])).values('file')[0]['file']
        except:
            pass

    def get_image_path(self):
        try:
            return File.objects.filter(id=(ProductImage.objects.filter(product_id=self.id).values('image_id')[0]['image_id'])).values('file')[0]['file']
        except:
            pass

    def catchphrases_as_string(self):
        catchphrase_list = list(self.catchphrases.all().values_list('name'))
        catchphrase_as_string = ""
        for e in catchphrase_list:
            catchphrase_as_string = catchphrase_as_string + ''.join(e) + " "
        return catchphrase_as_string
    
    def price_cleaned(self):
        p = self.unit_price
        return str(p)

    @property
    def sample_image(self):
        return self.images.first()


class ProductTranslation(TranslatedFieldsModel):
    master = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='translations',
        null=True,
    )

    caption = HTMLField(
        verbose_name=_("Caption"),
        blank=True,
        null=True,
        configuration='CKEDITOR_SETTINGS_CAPTION',
        help_text=_(
            "Short description used in the catalog's list view of products."),
    )

    class Meta:
        unique_together = [('language_code', 'master')]


class Commodity(AvailableProductMixin, Product):
    multilingual = TranslatedFields(
        description=HTMLField(
            verbose_name=_("Description"),
            configuration='CKEDITOR_SETTINGS_DESCRIPTION',
            help_text=_(
                "Full description used in the catalog's detail view of the product."),
        ),
    )

    # controlling the catalog
    placeholder = PlaceholderField("Commodity Details")
    show_breadcrumb = True  # hard coded to always show the product's breadcrumb

    class Meta:
        verbose_name = _("Commodity")
        verbose_name_plural = _("Commodities")

    default_manager = ProductManager()

    def get_price(self, request):
        return self.unit_price


class Video(AvailableProductMixin, Product):
    multilingual = TranslatedFields(
        description=HTMLField(
            verbose_name=_("Description"),
            configuration='CKEDITOR_SETTINGS_DESCRIPTION',
            help_text=_(
                "Full description used in the catalog's detail view of the product."),
        ),
    )

    allow_download = models.BooleanField(
        _("Downloadable"),
        default= False
    )

    download_percentage = models.PositiveIntegerField(
        _("Percentage added to download price"),
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _("Video")
        verbose_name_plural = _("Videos")
        ordering = ['order']

    # filter expression used to lookup for a product item using the Select2 widget
    lookup_fields = ['product_code__startswith', 'product_name__icontains']

    def get_price(self, request):
        return self.unit_price

    default_manager = ProductManager()


class Album(AvailableProductMixin, Product):
    multilingual = TranslatedFields(
        description=HTMLField(
            verbose_name=_("Description"),
            configuration='CKEDITOR_SETTINGS_DESCRIPTION',
            help_text=_(
                "Full description used in the catalog's detail view of the product."),
        ),
    )

    class Meta:
        verbose_name = _("Album")
        verbose_name_plural = _("Albums")

    def get_price(self, request):
        return self.unit_price

    default_manager = ProductManager()
