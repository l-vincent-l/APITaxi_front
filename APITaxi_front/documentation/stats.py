# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from flask import Blueprint, render_template, current_app
from flask.ext.security import current_user
from flask.ext.restful import request
from ..extensions import user_datastore
from APITaxi_models import db
from APITaxi_models.taxis import Taxi, ADS
from APITaxi_models.hail import Hail
from APITaxi_models.administrative import ZUPC
from APITaxi_models.security import User

mod = Blueprint('stats', __name__)

@mod.route('/stats')
def stats_index():

    dep = request.args.get('dep', 0, type=int)

    return render_template('stats.html',
                           dep=dep,
                           nb_taxis=stats_taxis(dep),
                           taxis=list_active_taxis(dep),
                           nb_hails=stats_hails(dep),
                           hails=list_hails(dep)
                          )

def stats_taxis(dep):

    depattern = '{0:02d}%'.format(dep) if dep else '%'
    last_day = datetime.now() + timedelta(days=-1)
    last_6months = datetime.now() + relativedelta(months=-6)


    nb_taxis = []
    nb_active_taxis = []
    tab_nb_taxis = defaultdict(dict)
    hidden_operator = User.query.filter_by(
        email=current_app.config.get('HIDDEN_OPERATOR', 'testing_operator')
    ).first()

    if current_user.has_role('admin'):
        nb_taxis = db.session.query(Taxi.added_by,
                                    func.count(Taxi.id).label('ntaxis'),
                                    func.count('0').label('nactivetaxis')) \
                   .join(Taxi.ads) \
                   .filter(ADS.insee.like(depattern)) \
                   .filter(Taxi.last_update_at >= last_6months) \
                   .group_by(Taxi.added_by)

        nb_active_taxis = db.session.query(Taxi.added_by,
                                           func.count('0').label('ntaxis'),
                                           func.count(Taxi.id).label('nactivetaxis')) \
                          .join(Taxi.ads) \
                          .filter(ADS.insee.like(depattern)) \
                          .filter(Taxi.last_update_at >= last_day) \
                          .group_by(Taxi.added_by)

    elif current_user.has_role('operateur'):
        nb_taxis = db.session.query(Taxi.added_by,
                                    func.count(Taxi.id).label('ntaxis'),
                                    func.count('0').label('nactivetaxis')) \
                   .join(Taxi.ads) \
                   .filter(ADS.insee.like(depattern)) \
                   .filter(Taxi.last_update_at >= last_6months) \
                   .filter(Taxi.added_by == current_user.id) \
                   .group_by(Taxi.added_by)

        nb_active_taxis = db.session.query(Taxi.added_by,
                                           func.count('0').label('ntaxis'),
                                           func.count(Taxi.id).label('nactivetaxis')) \
                          .join(Taxi.ads) \
                          .filter(ADS.insee.like(depattern)) \
                          .filter(Taxi.last_update_at >= last_day) \
                          .filter(Taxi.added_by == current_user.id) \
                          .group_by(Taxi.added_by)

    if not tab_nb_taxis:
        nb_taxis = db.session.query(
                                    func.count(Taxi.id).label('ntaxis'),
                                    func.count('0').label('nactivetaxis')) \
                   .join(Taxi.ads) \
                   .filter(ADS.insee.like(depattern)) \
                   .filter(Taxi.last_update_at >= last_6months)

        nb_active_taxis = db.session.query(
                                           func.count('0').label('ntaxis'),
                                           func.count(Taxi.id).label('nactivetaxis')) \
                          .join(Taxi.ads) \
                          .filter(ADS.insee.like(depattern)) \
                          .filter(Taxi.last_update_at >= last_day)

    if hidden_operator:
        nb_taxis = nb_taxis.filter(Taxi.added_by != hidden_operator.id)
        nb_active_taxis = nb_active_taxis.filter(Taxi.added_by != hidden_operator.id)

    if tab_nb_taxis:
        for ta in nb_taxis:
            tab_nb_taxis[user_datastore.get_user(ta.added_by).commercial_name]['ntaxis'] = ta.ntaxis
        for ta in nb_active_taxis:
            tab_nb_taxis[user_datastore.get_user(ta.added_by).commercial_name]['nactivetaxis'] = ta.nactivetaxis


    tab_nb_taxis['Total']['ntaxis'] = 0
    tab_nb_taxis['Total']['nactivetaxis'] = 0
    for ta in nb_taxis:
        tab_nb_taxis['Total']['ntaxis'] += ta.ntaxis
    for ta in nb_active_taxis:
        tab_nb_taxis['Total']['nactivetaxis'] += ta.nactivetaxis

    return tab_nb_taxis


def list_active_taxis(dep):
    if not current_user.has_role('admin') and not current_user.has_role('operateur'):
        return defaultdict(dict)

    depattern = '{0:02d}%'.format(dep) if dep else '%'
    last_day = datetime.now() + timedelta(days=-1)

    taxis = []
    hidden_operator = User.query.filter_by(
        email=current_app.config.get('HIDDEN_OPERATOR', 'testing_operator')
    ).first()

    taxis = Taxi.query.join(User).join(Taxi.ads) \
            .filter(ADS.insee.like(depattern)) \
            .filter(Taxi.last_update_at >= last_day)
    if not current_user.has_role('admin'):
        taxis = taxis.filter(Taxi.added_by == current_user.id)

    if hidden_operator:
        taxis = taxis.filter(Taxi.added_by != hidden_operator.id)

    taxis = taxis.order_by(Taxi.added_by).limit(20).all()

    tab_taxis = defaultdict(dict)
    for taxi in taxis:
        tab_taxis[taxi.id]['added_by'] = user_datastore.get_user(taxi.added_by).commercial_name
        tab_taxis[taxi.id]['ads.insee'] = taxi.ads.insee
        zupc = None
        zupc = ZUPC.query.filter_by(insee=taxi.ads.insee).order_by(ZUPC.id.desc()).first()
        if zupc:
            tab_taxis[taxi.id]['zupc.nom'] = zupc.nom
        else:
            tab_taxis[taxi.id]['zupc.nom'] = ''
        tab_taxis[taxi.id]['ads.numero'] = taxi.ads.numero
        tab_taxis[taxi.id]['driver.professional_licence'] = taxi.driver.professional_licence
        tab_taxis[taxi.id]['last_update_at'] = taxi.last_update_at

    return tab_taxis


def stats_hails(dep):

    depattern = '{0:02d}%'.format(dep) if dep else '%'

    last_day = datetime.now() + timedelta(days=-1)
    last_year = datetime.now() + relativedelta(months=-12)

    nb_hails_d = []
    nb_hails_ok_d = []
    nb_hails_y = []
    nb_hails_ok_y = []
    tab_nb_hails = defaultdict(dict)

    if current_user.has_role('admin'):

        nb_hails_d = db.session.query(Hail.operateur_id,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_day) \
                     .group_by(Hail.operateur_id) \

        nb_hails_ok_d = db.session.query(Hail.operateur_id,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_day) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .group_by(Hail.operateur_id) \

        nb_hails_y = db.session.query(Hail.operateur_id,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_year) \
                     .group_by(Hail.operateur_id) \

        nb_hails_ok_y = db.session.query(Hail.operateur_id,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_year) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .group_by(Hail.operateur_id) \

        for ha in nb_hails_d:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_d'] = ha.nhails
        for ha in nb_hails_ok_d:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_ok_d'] = ha.nhails
        for ha in nb_hails_y:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_y'] = ha.nhails
        for ha in nb_hails_ok_y:
            tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_ok_y'] = ha.nhails

    elif current_user.has_role('operateur'):

        nb_hails_d = db.session.query(Hail.added_by,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_day) \
                     .filter(Hail.operateur_id == current_user.id) \
                     .group_by(Hail.added_by) \

        nb_hails_ok_d = db.session.query(Hail.added_by,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_day) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .filter(Hail.operateur_id == current_user.id) \
                        .group_by(Hail.added_by) \

        nb_hails_y = db.session.query(Hail.added_by,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_year) \
                     .filter(Hail.operateur_id == current_user.id) \
                     .group_by(Hail.added_by) \

        nb_hails_ok_y = db.session.query(Hail.added_by,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_year) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .filter(Hail.operateur_id == current_user.id) \
                        .group_by(Hail.added_by) \

        for ha in nb_hails_d:
             tab_nb_hails[user_datastore.get_user(ha.added_by).email]['nhails_d'] = ha.nhails
        for ha in nb_hails_ok_d:
             tab_nb_hails[user_datastore.get_user(ha.added_by).email]['nhails_ok_d'] = ha.nhails
        for ha in nb_hails_y:
             tab_nb_hails[user_datastore.get_user(ha.added_by).email]['nhails_y'] = ha.nhails
        for ha in nb_hails_ok_y:
             tab_nb_hails[user_datastore.get_user(ha.added_by).email]['nhails_ok_y'] = ha.nhails


    elif current_user.has_role('moteur'):

        nb_hails_d = db.session.query(Hail.operateur_id,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_day) \
                     .filter(Hail.added_by == current_user.id) \
                     .group_by(Hail.operateur_id) \

        nb_hails_ok_d = db.session.query(Hail.operateur_id,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_day) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .filter(Hail.added_by == current_user.id) \
                        .group_by(Hail.operateur_id) \

        nb_hails_y = db.session.query(Hail.operateur_id,
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_year) \
                     .filter(Hail.added_by == current_user.id) \
                     .group_by(Hail.operateur_id) \

        nb_hails_ok_y = db.session.query(Hail.operateur_id,
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_year) \
                        .filter(Hail._status == 'accepted_by_customer') \
                        .filter(Hail.added_by == current_user.id) \
                        .group_by(Hail.operateur_id) \

        for ha in nb_hails_d:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_d'] = ha.nhails
        for ha in nb_hails_ok_d:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_ok_d'] = ha.nhails
        for ha in nb_hails_y:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_y'] = ha.nhails
        for ha in nb_hails_ok_y:
             tab_nb_hails[user_datastore.get_user(ha.operateur_id).commercial_name]['nhails_ok_y'] = ha.nhails


    if not tab_nb_hails:

        nb_hails_d = db.session.query(
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_day) \

        nb_hails_ok_d = db.session.query(
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_day) \
                        .filter(Hail._status == 'accepted_by_customer') \

        nb_hails_y = db.session.query(
                                      func.count(Hail.id).label('nhails')) \
                     .join(Hail.taxi_relation) \
                     .join(Taxi.ads) \
                     .filter(ADS.insee.like(depattern)) \
                     .filter(Hail.creation_datetime >= last_year) \

        nb_hails_ok_y = db.session.query(
                                         func.count(Hail.id).label('nhails')) \
                        .join(Hail.taxi_relation) \
                        .join(Taxi.ads) \
                        .filter(ADS.insee.like(depattern)) \
                        .filter(Hail.creation_datetime >= last_year) \
                        .filter(Hail._status == 'accepted_by_customer') \

    
    tab_nb_hails['Total']['nhails_d'] = 0
    tab_nb_hails['Total']['nhails_ok_d'] = 0
    tab_nb_hails['Total']['nhails_y'] = 0
    tab_nb_hails['Total']['nhails_ok_y'] = 0

    hidden_operator = User.query.filter_by(
        email=current_app.config.get('HIDDEN_OPERATOR', 'testing_operator')
    ).first()
    hidden_moteur = User.query.filter_by(
        email=current_app.config.get('HIDDEN_MOTEUR', 'testing_moteur')
    ).first()

    if hidden_operator:
        nb_hails_d = nb_hails_d.filter(Hail.operateur_id != hidden_operator.id)
        nb_hails_ok_d = nb_hails_ok_d.filter(Hail.operateur_id != hidden_operator.id)
        nb_hails_y = nb_hails_y.filter(Hail.operateur_id != hidden_operator.id)
        nb_hails_ok_y = nb_hails_ok_y.filter(Hail.operateur_id != hidden_operator.id)
    if hidden_moteur:
        nb_hails_d = nb_hails_d.filter(Hail.added_by != hidden_moteur.id)
        nb_hails_ok_d = nb_hails_ok_d.filter(Hail.added_by != hidden_moteur.id)
        nb_hails_y = nb_hails_y.filter(Hail.added_by != hidden_moteur.id)
        nb_hails_ok_y = nb_hails_ok_y.filter(Hail.added_by != hidden_moteur.id)

    for ha in nb_hails_d:
        tab_nb_hails['Total']['nhails_d'] += ha.nhails
    for ha in nb_hails_ok_d:
        tab_nb_hails['Total']['nhails_ok_d'] += ha.nhails
    for ha in nb_hails_y:
        tab_nb_hails['Total']['nhails_y'] += ha.nhails
    for ha in nb_hails_ok_y:
        tab_nb_hails['Total']['nhails_ok_y'] += ha.nhails

    return tab_nb_hails


def list_hails(dep):
    if not current_user.has_role('admin') and\
       not current_user.has_role('operateur') and not current_user.has_role('moteur'):
        return defaultdict(dict)

    depattern = '{0:02d}%'.format(dep) if dep else '%'
    hails = []

    last_year = datetime.now() + relativedelta(months=-12)

    hails = db.session.query(Hail.operateur_id, Hail.added_by,
                             Hail.creation_datetime, Hail.id,
                             ADS.insee, ADS.numero, Hail._status) \
                 .join(Hail.taxi_relation) \
                 .join(Taxi.ads) \
                 .filter(ADS.insee.like(depattern)) \
                 .filter(Hail.creation_datetime >= last_year)

    if current_user.has_role('operateur'):
        hails = hails.filter(Hail.operateur_id == current_user.id)
    elif current_user.has_role('moteur'):
        hails = hails.filter(Hail.added_by == current_user.id)
    hidden_operator = User.query.filter_by(
        email=current_app.config.get('HIDDEN_OPERATOR', 'testing_operator')
    ).first()
    hidden_moteur = User.query.filter_by(
        email=current_app.config.get('HIDDEN_MOTEUR', 'testing_moteur')
    ).first()

    if hidden_operator:
        hails = hails.filter(Hail.operateur_id != hidden_operator.id)
    if hidden_moteur:
        hails = hails.filter(Hail.added_by != hidden_moteur.id)
    hails = hails.order_by(Hail.creation_datetime.desc()).limit(100).all()

    tab_hails = defaultdict(dict)
    for hail in hails:
        tab_hails[hail.id]['creation_datetime'] = hail.creation_datetime
        # tab_hails[hail.id]['added_by'] = user_datastore.get_user(hail.added_by).commercial_name
        tab_hails[hail.id]['added_by'] = user_datastore.get_user(hail.added_by).email
        tab_hails[hail.id]['operator'] = user_datastore.get_user(hail.operateur_id).commercial_name
        tab_hails[hail.id]['ads.insee'] = hail.insee
        zupc = None
        zupc = ZUPC.query.filter_by(insee=hail.insee).order_by(ZUPC.id.desc()).first()
        if zupc:
            tab_hails[hail.id]['zupc.nom'] = zupc.nom
        else:
            tab_hails[hail.id]['zupc.nom'] = ''
        tab_hails[hail.id]['ads.numero'] = hail.numero
        tab_hails[hail.id]['last_status'] = hail._status

    return tab_hails

