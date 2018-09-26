# -*- coding: utf-8 -*-
from APITaxi_models import security as security_models
from .forms.user import UserForm

from flask_security import login_required, roles_accepted, current_user
from flask import (Blueprint, request, render_template, redirect, jsonify,
                   url_for, abort, current_app, send_file)
from APITaxi_utils import fields
from flask_restplus import fields as basefields, marshal_with, Resource
import os, uuid
from PIL import Image

mod = Blueprint('profile', __name__)
@mod.route('/user/form', methods=['GET', 'POST'])
@login_required
def profile_form():
    form = None
    form = UserForm(obj=current_user)
    if not current_user.has_role('operateur') and not current_user.has_role('moteur'):
        del form._fields['commercial_name']
    if not current_user.has_role('operateur'):
        del form._fields['logo']
        del form._fields['hail_endpoint_staging']
        del form._fields['hail_endpoint_testing']
        del form._fields['hail_endpoint_production']
    if current_user.has_role('prefecture'):
        del form._fields['email_technical']
        del form._fields['phone_number_technical']
        form._fields['email_customer'].description = 'Adresse email de contact'
        form._fields['email_customer'].label.text = form._fields['email_customer'].description
        form._fields['phone_number_customer'].description = 'Numéro de téléphone de contact'
        form._fields['phone_number_customer'].label.text = \
                form._fields['phone_number_customer'].description

    if request.method == "POST" and form.validate():
        user = security_models.User.query.get(current_user.id)
        if current_user.has_role('operateur'):
            logo = form.logo
            if logo and logo.has_file():
                id_ = str(uuid.uuid4())
                file_dest = os.path.join(current_app.config['UPLOADED_IMAGES_DEST'],
                            id_)
                logo.data.save(file_dest)
                image = Image.open(file_dest)
                logo_db = security_models.Logo(id=id_, size=image.size,
                    format_=image.format, user_id=user.id)
                current_app.extensions['sqlalchemy'].db.session.add(logo_db)
                user.logos.append(logo_db)
        form.populate_obj(user)
        current_app.extensions['sqlalchemy'].db.session.add(user)
        current_app.extensions['sqlalchemy'].db.session.commit()
        return redirect(url_for('profile.profile_form'))
    return render_template('forms/profile.html', form=form,
        form_method="POST", logos=current_user.logos, submit_value="Modifier",
        )

class LogoHref(basefields.Raw):
    def output(self, key, obj):
        return url_for('profile.image', user_id=obj.user_id, src=obj.id)

@mod.route('/user/<int:user_id>/images/<src>')
def image(user_id, src):
    logo = security_models.Logo.query.get(src)
    if not logo:
        abort(404, message="Unable to find the logo")
    if not logo.user_id == user_id:
        abort(404, message="Unable to find the logo")
    return send_file(os.path.join(current_app.config['UPLOADED_IMAGES_DEST'],
        logo.id))
