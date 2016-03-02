# -*- coding: utf-8 -*-
# (c) 2015 Ainara Galdona - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import models, fields, api
from openerp.addons import decimal_precision as dp


class MrpRepairLine(models.Model):

    _inherit = 'mrp.repair.line'

    @api.multi
    @api.depends('product_id', 'product_uom_qty', 'lot_id', 'expected_qty',
                 'to_invoice')
    def _compute_cost_subtotal(self):
        super(MrpRepairLine, self)._compute_cost_subtotal()
        for line in self:
            qty = line.product_uom_qty
            if line.to_invoice:
                qty = line.expected_qty
            line.cost_subtotal = line.standard_price * qty

    @api.multi
    @api.depends('expected_qty', 'product_uom_qty', 'price_unit', 'product_id',
                 'tax_id', 'repair_id.partner_id', 'to_invoice',
                 'repair_id.pricelist_id.currency_id')
    def _get_line_subtotal(self):
        for line in self:
            qty = line.product_uom_qty
            if line.to_invoice:
                qty = line.expected_qty
            taxes = line.tax_id.compute_all(
                line.price_unit, qty, line.product_id,
                line.repair_id.partner_id)
            cur = line.repair_id.pricelist_id.currency_id
            subtotal = cur.round(taxes['total'])
            line.price_subtotal = subtotal

    expected_qty = fields.Float(string='Expected Qty',
                                digits=dp.get_precision(
                                    'Product Unit of Measure'))
    product_uom_qty = fields.Float(string='Real Qty', default=0)
    price_subtotal = fields.Float(compute='_get_line_subtotal')
    repair_state = fields.Selection([
        ('draft', 'Quotation'),
        ('cancel', 'Cancelled'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('2binvoiced', 'To be Invoiced'),
        ('invoice_except', 'Invoice Exception'),
        ('done', 'Repaired')
        ], related="repair_id.state")

    @api.multi
    def write(self, vals):
        res = super(MrpRepairLine, self).write(vals)
        inv_line_obj = self.env['account.invoice.line']
        for line in self:
            if vals.get('invoiced', False) and line.expected_qty and \
                    vals.get('invoice_line_id', False):
                invoice_line = inv_line_obj.browse(vals.get('invoice_line_id'))
                invoice_line.write({'quantity': self.expected_qty})
        return res

    def product_id_change(self, cr, uid, ids, pricelist, product, uom=False,
                          product_uom_qty=0, partner_id=False,
                          guarantee_limit=False, context=None):
        res = super(MrpRepairLine, self).product_id_change(
            cr, uid, ids, pricelist, product, uom=uom,
            product_uom_qty=product_uom_qty, partner_id=partner_id,
            guarantee_limit=guarantee_limit, context=context)
        if context.get('default_repair_state', False) == 'draft':
            res['value']['product_uom_qty'] = 0
            res['value']['expected_qty'] = context.get('repair_qty', 0)
        else:
            res['value']['product_uom_qty'] = context.get('repair_qty', 0)
            res['value']['expected_qty'] = 0
        return res


class MrpRepair(models.Model):

    _inherit = 'mrp.repair'

    def _catch_repair_line_information_for_analytic(self, line):
        res = super(MrpRepair,
                    self)._catch_repair_line_information_for_analytic(line)
        ctx = self.env.context
        load_estim = ctx.get('load_estimated', False)
        if line._name == 'mrp.repair.line' and load_estim and \
                not line.expected_qty:
            return False
        elif line._name == 'mrp.repair.line' and line.cost_subtotal and \
                load_estim and line.expected_qty:
            # siempre habra un res, si hay line.cost_subtotal
            res['unit_amount'] = line.expected_qty
            res['repair_estim_amount'] = (line.cost_subtotal * -1)
            res['amount'] = 0
        return res
