# -*- coding: utf-8 -*-
from flask import Blueprint, render_template
from flask_security import current_user

mod = Blueprint('documentation', __name__)

@mod.route('/documentation/interface')
def doc_interface():
    return render_template('documentation/interface.html',
             apikey='token' if current_user.is_anonymous else current_user.apikey)
