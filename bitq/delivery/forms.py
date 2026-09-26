from django import forms

from .models import Item


class MenuItemForm(forms.ModelForm):
    price = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0.01)
    picture = forms.URLField(max_length=400, required=False)

    class Meta:
        model = Item
        fields = ('name', 'description', 'price', 'vegeterian', 'picture')
        labels = {
            'vegeterian': 'Vegetarian',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_description(self):
        return self.cleaned_data['description'].strip()

    def clean_picture(self):
        return self.cleaned_data.get('picture') or Item._meta.get_field('picture').get_default()