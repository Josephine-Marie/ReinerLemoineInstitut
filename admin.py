from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.template.context import Context
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin, TranslatableInlineModelAdmin
from filer.models import ThumbnailOption
from adminsortable2.admin import SortableAdminMixin, PolymorphicSortableAdminMixin, SortableInlineAdminMixin
from cms.admin.placeholderadmin import PlaceholderAdminMixin, FrontendEditableAdminMixin
from shop.admin.customer import CustomerAdminBase, CustomerInlineAdminBase, CustomerProxy
from shop.admin.defaults.order import OrderAdmin
from shop.models.defaults.order import Order
from shop.admin.order import PrintInvoiceAdminMixin
from shop.admin.delivery import DeliveryOrderAdminMixin
from shop_sendcloud.admin import SendCloudOrderAdminMixin
from shop.admin.product import CMSPageAsCategoryMixin, UnitPriceMixin, ProductImageInline, InvalidateProductCacheMixin, SearchProductIndexMixin, CMSPageFilter
from polymorphic.admin import (PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
                               PolymorphicChildModelFilter)
from ssccms.models import Customer, Product, Commodity, Video, Album, Catchphrase
from ssccms.related import ProductVideoModel, ProductSubtitlesModel

admin.site.site_header = "SSCCMS Administration"

admin.site.index_template = "admin/adminindex.html"
#admin.site.login_template= "admin/accounts/login.html"

admin.site.unregister(ThumbnailOption)
admin.site.register(Catchphrase, admin.ModelAdmin)

UserAdmin.search_fields = ('username', 'first_name', 'last_name', 'email', 'customer__videocode')
UserAdmin.fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active',),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

__all__ = ['customer']

class CustomerInlineAdmin(CustomerInlineAdminBase):
    fieldsets = [
        (None, {'fields': ['salutation','birth_date','adult']}),
        (None, {'fields': ['coins','newsletter_subscription', 'videoupload_notification','videocode']}),
        #(_("Addresses"), {'fields': ['get_shipping_addresses', 'get_billing_addresses']}),
    ]

    readonly_fields = ['coins','videocode']
    search_fields = ('videocode',)

    def get_number(self, customer):
        return customer.get_number() or '–'
    get_number.short_description = _("Customer Number")

    def get_shipping_addresses(self, customer):
        addresses = [(a.as_text(),) for a in customer.shippingaddress_set.all()]
        return format_html_join('', '<address>{0}</address>', addresses)
    get_shipping_addresses.short_description = _("Shipping")


@admin.register(CustomerProxy)
class CustomerAdmin(CustomerAdminBase, TranslatableAdmin):
    class Media:
        css = {'all': ['shop/css/admin/customer.css']}

    inlines = [CustomerInlineAdmin]

    def get_list_display(self, request):
        #list_display are the attributes/header shown in the table
        list_display = list(super().get_list_display(request))
        list_display.insert(1, 'salutation')
        return list_display

    def salutation(self, user):
        if hasattr(user, 'customer'):
            return user.customer.get_salutation_display()
        return ''
    salutation.short_description = _("Salutation")
    salutation.admin_order_field = 'customer__salutation'


@admin.register(Order)
class OrderAdmin(PrintInvoiceAdminMixin, SendCloudOrderAdminMixin, DeliveryOrderAdminMixin, OrderAdmin):
    pass


@admin.register(Commodity)
class CommodityAdmin(InvalidateProductCacheMixin, SearchProductIndexMixin, SortableAdminMixin, TranslatableAdmin, FrontendEditableAdminMixin,
                     PlaceholderAdminMixin, CMSPageAsCategoryMixin, PolymorphicChildModelAdmin):
    base_model = Product
    fields = [
        ('product_name', 'slug'),
        'unit_price', 
        'quantity',
        'catchphrases',
        'active',
        'caption',
        'description'
    ]
    filter_horizontal = ['cms_pages']
    inlines = [ProductImageInline]
    prepopulated_fields = {'slug': ['product_name']}


# Inlines to enable the admin to upload Files directly from the "new Video" Page
class ProductVideoInline(SortableInlineAdminMixin, admin.StackedInline):
    model = ProductVideoModel
    extra = 1


class ProductSubtitlesInline(SortableInlineAdminMixin, admin.StackedInline):
    model = ProductSubtitlesModel
    extra = 1


@admin.register(Video)
class VideoAdmin(InvalidateProductCacheMixin, SearchProductIndexMixin, SortableAdminMixin, TranslatableAdmin, FrontendEditableAdminMixin,
                     CMSPageAsCategoryMixin, PlaceholderAdminMixin, PolymorphicChildModelAdmin):
    base_model = Product
    fieldsets = (
        (None, {
            'fields': [
                ('product_name', 'slug'),
                'unit_price',
                'catchphrases',
                'active',
                'allow_download',
                'download_percentage'
            ],
        }),
        (_("Translatable Fields"), {
            'fields': ['caption', 'description'],
        })
    )
    filter_horizontal = ['cms_pages']
    inlines = [ProductImageInline, ProductVideoInline, ProductSubtitlesInline]
    prepopulated_fields = {'slug': ['product_name']}


@admin.register(Album)
class AlbumAdmin(InvalidateProductCacheMixin, SearchProductIndexMixin, SortableAdminMixin, TranslatableAdmin, FrontendEditableAdminMixin,
                      CMSPageAsCategoryMixin, PlaceholderAdminMixin, PolymorphicChildModelAdmin):
    base_model = Product
    fieldsets = [
        (None, {
            'fields': [
                ('product_name', 'slug'),
                'unit_price',
                'catchphrases',
                'active'
            ],
        }),
        (_("Translatable Fields"), {
            'fields': ['caption', 'description'],
        })
    ]
    filter_horizontal = ['cms_pages']
    prepopulated_fields = {'slug': ['product_name']}

    def render_text_index(self, instance):
        template = get_template('search/indexes/ssccms/commodity_text.txt')
        return template.render(Context({'object': instance}))
    render_text_index.short_description = _("Text Index")


@admin.register(Product)
class ProductAdmin(PolymorphicSortableAdminMixin, PolymorphicParentModelAdmin):
    base_model = Product
    child_models = [Commodity, Video, Album]
    list_display = ['product_name', 'get_price', 'product_type', 'active']
    list_display_links = ['product_name']
    search_fields = ['product_name']
    list_filter = [PolymorphicChildModelFilter, CMSPageFilter]
    list_per_page = 250
    list_max_show_all = 1000

    def get_price(self, obj):
        return str(obj.get_real_instance().get_price(None))

    get_price.short_description = _("Price starting at")
