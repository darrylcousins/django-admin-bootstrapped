# -*- coding: utf-8 -*-
from itertools import chain

from django import forms
from django.conf import settings
from django.forms.utils import flatatt
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils import formats
from django.template.loader import render_to_string
from django.utils.datastructures import MultiValueDict, MergeDict
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse, NoReverseMatch
from django.forms.widgets import Select


def silent_reverse(url):
    try:
        return reverse(url)
    except NoReverseMatch:
        return ''


class GenericContentTypeSelect(Select):
    allow_multiple_selected = False

    def render_option(self, selected_choices, option_value, option_label):
        option_value = force_text(option_value)
        extra_attrs = {}
        if option_value:
            ct = ContentType.objects.get(pk=option_value)
            extra_attrs = {
                'data-generic-lookup-enabled': 'yes',
                'data-admin-url': silent_reverse(
                    'admin:{0.app_label}_'
                    '{0.name}_changelist'.format(ct)),
            }

        if option_value in selected_choices:
            selected_html = mark_safe(' selected="selected"')
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''
        return format_html('<option value="{0}"{1} {2}>{3}</option>',
                           option_value,
                           selected_html,
                           mark_safe(
                               ' '.join(['{0}="{1}"'.format(k, v) for k, v in extra_attrs.items()])),
                           force_text(option_label))

    class Media(object):
        js = ('admin/js/generic-lookup.js', )


class SmallTextareaWidget(forms.Textarea):
    """
    Use a smaller text area in the admin views.

        >>> textarea = SmallTextareaWidget()
        >>> textarea
        <biomarker.biobase.widgets.SmallTextareaWidget object at ...>

    Renders with cols=20 and rows=4::

        >>> textarea.render('name', 'value')
        '<textarea class="vTextField" cols="20" name="name" rows="4">...value</textarea>'

    """
    def __init__(self, attrs=None):
        final_attrs = {'class': 'vTextField', 'cols': '20', 'rows': '4'}
        if attrs is not None:
            final_attrs.update(attrs)
        super(SmallTextareaWidget, self).__init__(attrs=final_attrs)


class AutocompleteSelectWidget(forms.Select):
    """
    A autocomplete select widget to replace dropdown foreign key select widget
    for admin screens.

        >>> autocomplete = AutocompleteSelectWidget()
        >>> autocomplete
        <biomarker.biobase.widgets.AutocompleteSelectWidget object at ...>

    Renders with input field and bootstrap modal


    """
    allow_multiple_selected = False
    input_type = 'text'

    class Media:
        js = (
            '//ajax.googleapis.com/ajax/libs/jqueryui/1.10.4/jquery-ui.min.js',
            settings.STATIC_URL + 'js/autocomplete_select.js',
            settings.STATIC_URL + 'js/loading.js',
            )
        css = {
            'screen': (settings.STATIC_URL + 'css/autocomplete.css', )
            }

    def _format_value(self, value):
        if self.is_localized:
            return formats.localize_input(value)
        return value

    def value_from_datadict(self, data, files, name):
        """
        Given a dictionary of data and this widget's name, returns the value
        of it paired hidden field.
        """
        name = '%(name)s_select' % dict(name=name)
        return data.get(name, None)

    def render(self, name, value, attrs={}, choices=()):
        """
        Renders two input fields along with a modal and javascript.

        The hidden input holds the pk value of the fk and will be collected on
        submission of form.
        """
        model = self.choices.field.queryset.model
        title = model._meta.verbose_name_plural
        if value is None:
            value = ''
            str_value = ''
        else:
            str_value = str(model.objects.get(pk=value))
            str_value = force_text(self._format_value(str_value))
        final_attrs = self.build_attrs(attrs, name=name)
        final_attrs['data-relation'] = name
        final_attrs['title'] = title
        final_attrs = self.build_attrs(attrs, type=self.input_type, name=name)
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_text(self._format_value(str_value))
        final_attrs['class'] = 'autocomplete-select form-control'
        final_attrs['style'] = 'display:inline-block'
        final_attrs['placeholder'] = str(_('Search ...'))

        output = []
        output.append('<input id="%(name)s_select" type="hidden" name="%(name)s_select" value="%(value)s">' % dict(
            name=name, value=value))

        output.append(format_html('<input{0} />', flatatt(final_attrs)))
        # only init if not a inline template form
        if '__prefix__' not in name:
            output.append('<script type="text/javascript">')
            output.append('(function($) {')
            output.append('if (window.AutocompleteSearch != undefined) {')
            output.append('AutocompleteSearch.init("%(id_)s", "%(name)s", "%(title)s");' % dict(
                name=name,
                title=title,
                id_=final_attrs['id']))
            output.append('}')
            output.append('}(jQuery));')
            output.append('</script>')

        return mark_safe('\n'.join(output))


class AutocompleteSelectMulitpleWidget(forms.SelectMultiple):
    """
    A autocomplete select widget to replace dropdown foreign key select widget
    for admin screens.

        >>> autocomplete = AutocompleteSelectMulitpleWidget()
        >>> autocomplete
        <biomarker.biobase.widgets.AutocompleteSelectMulitpleWidget object at ...>

    Renders with input field and bootstrap modal


    """
    allow_multiple_selected = True

    class Media:
        js = (
            '//ajax.googleapis.com/ajax/libs/jqueryui/1.10.4/jquery-ui.min.js',
            settings.STATIC_URL + 'js/autocomplete_multipleselect.js',
            settings.STATIC_URL + 'js/loading.js',
            )
        css = {
            'screen': (settings.STATIC_URL + 'css/autocomplete.css', )
            }

    def value_from_datadict(self, data, files, name):
        """
        Shouldn't need to override this - make note if you do!!
        """
        if isinstance(data, (MultiValueDict, MergeDict)):
            return data.getlist(name)
        return data.get(name, None)

    def render_options(self, choices, selected_choices):
        # Normalize to strings.
        selected_choices = set(force_text(v) for v in selected_choices)
        output = []
        for option_value, option_label in chain(self.choices, choices):
            # only list selected choices in select field
            if str(option_value) in selected_choices:
                if isinstance(option_label, (list, tuple)):
                    output.append(format_html('<optgroup label="{0}">', force_text(option_value)))
                    for option in option_label:
                        # not passing selected values to render
                        output.append(self.render_option([], *option))
                    output.append('</optgroup>')
                else:
                    # not passing selected values to render
                    output.append(self.render_option([], option_value, option_label))
        return '\n'.join(output)

    def render(self, name, value, attrs=None, choices=()):
        model = self.choices.field.queryset.model
        verbose_name_plural = model._meta.verbose_name_plural
        verbose_name = model._meta.verbose_name
        if value is None:
            value = []

        output = ['<div class="btn-group">']
        output.append('<button class="btn btn-default" role="button" id="add_%s">' % name)
        output.append('Add %s</button>' % verbose_name)
        output.append('<button class="btn btn-default disabled" role="button" id="remove_%s">' % name)
        output.append('Remove selected</button>')
        output.append('</div>')
        output.append('<div class="control-group">&nbsp;</div>')

        final_attrs = self.build_attrs(attrs, name=name)
        del final_attrs['title']
        final_attrs['class'] = 'autocomplete-multipleselect form-control'
        output.append(format_html('<select multiple="multiple"{0}>', flatatt(final_attrs)))
        options = self.render_options(choices, value)
        if options:
            output.append(options)
        output.append('</select>')

        # only init if not a inline template form
        if '__prefix__' not in name:
            output.append('<script type="text/javascript">')
            output.append('(function($) {')
            output.append('if (window.AutocompleteMultipleSearch != undefined) {')
            output.append('AutocompleteMultipleSearch.init("%(id_)s", "%(name)s", "%(title)s");' % dict(
                name=name,
                title=verbose_name_plural,
                id_=final_attrs['id']))
            output.append('}')
            output.append('}(jQuery));')
            output.append('</script>')

        return mark_safe('\n'.join(output))

        return mark_safe(render_to_string('autocomplete/multipleselect.html', {
            'name': name,
            'id': final_attrs['id'],
            'verbose_name': verbose_name,
            'verbose_name_plural': verbose_name_plural,
            'select': mark_safe('\n'.join(output)),
            'init': '__prefix__' not in name,
        }))
