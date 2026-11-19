String.prototype.width = function(font) {
    var f = font || '12px arial',
        o = $('<div></div>')
              .text(this)
              .css({'position': 'absolute', 'float': 'left', 'white-space': 'nowrap', 'visibility': 'hidden', 'font': f})
              .appendTo($('body')),
        w = o.width();

    o.remove();

    return w;
  }

let arrowWidth = 40;
$.fn.resizeselect = function(settings) {
    return this.each(function() {
        let maxWidth = 0;
        $(this).find('option').each(function() {
            let $this = $(this);
            // get font-weight, font-size, and font-family
            let style = window.getComputedStyle(this)
            let { fontWeight, fontSize, fontFamily } = style

            // create test element
            let text = $this.text();
            let $test = $('<div></div>')
              .text(text)
              .css({'position': 'absolute', 'float': 'left', 'white-space': 'nowrap', 'visibility': 'hidden', "font-size": fontSize, "font-weight": fontWeight, "font-family": fontFamily,})
              .appendTo($('body'));

            let width = $test.width();
            if (width > maxWidth) {
                maxWidth = width;
            }
            $test.remove();

            // set select width
            // $this.width(width + arrowWidth);
        });
        // console.log('maxWidth', maxWidth);
        $(this).width(maxWidth + arrowWidth);
    });
  };

$(document).ready(function() {
    $("select.resizeselect").resizeselect();
    showMessages();
    if (location.hash) {
        $("button[data-bs-target='" + location.hash + "']").tab("show");
    }
    $(document.body).on("click", "button[data-bs-toggle='tab']", function(event) {
        location.hash = this.getAttribute("data-bs-target");
    });
    // $("#customer-order-form-130").dirty();
    $(".customer-order-form").each(function(){
        console.log("preventLeaving", !$(this).hasClass('existing-order'));
        $(this).dirty({
            preventLeaving: $(this).hasClass('prevent-leaving'),
            leavingMessage: 'Du hast deinen Brotkorb noch nicht abgeschickt. Willst du wirklich die Seite verlassen?',
        });
    });
});
$(window).on("popstate", function() {
    var anchor = location.hash || $("button[data-bs-toggle='tab']").first().attr("data-bs-target");
    $("button[data-bs-target='" + anchor + "']").tab("show");
});

var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
  return new bootstrap.Popover(popoverTriggerEl)
})


// Messages from the server, hidden again after a few seconds. A toast that
// was closed already isn't shown again.
function showMessages() {
    document.querySelectorAll("#messages .toast:not(.hide)").forEach(function(toastEl) {
        bootstrap.Toast.getOrCreateInstance(toastEl, {delay: 6000}).show();
    });
}

// Mobile sidebar: a drawer opened from the button in the top left corner, closed with the close
// button, a tap on the backdrop or Escape.
var sidebarToggle = document.querySelector(".mobile-menu-toggle");

function setSidebarOpen(open) {
    document.body.classList.toggle("sidebar-open", open);
    if (sidebarToggle) sidebarToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
        var close = document.querySelector(".sidebar-close");
        if (close) close.focus();
    } else if (sidebarToggle && document.activeElement && document.activeElement.closest(".sidebar")) {
        sidebarToggle.focus();
    }
}

if (sidebarToggle) {
    sidebarToggle.addEventListener("click", function() {
        setSidebarOpen(true);
    });
}
document.addEventListener("click", function(event) {
    if (event.target.closest("[data-sidebar-close]")) setSidebarOpen(false);
});
document.addEventListener("keydown", function(event) {
    if (event.key === "Escape" && document.body.classList.contains("sidebar-open")) setSidebarOpen(false);
});

// Sidebar from md up: collapses to its icons. The state is a cookie, so the
// next page comes collapsed from the server without flicker. Collapsed, the
// labels show as tooltips to the right of the icons.
function sidebarLinks() {
    return document.querySelectorAll("#workshop-sidebar .nav-link");
}

document.addEventListener("click", function(event) {
    var button = event.target.closest("[data-sidebar-collapse]");
    if (!button) return;
    var sidebar = document.getElementById("workshop-sidebar");
    var collapsed = !sidebar.classList.contains("is-collapsed");
    sidebar.classList.toggle("is-collapsed", collapsed);
    button.setAttribute("aria-expanded", collapsed ? "false" : "true");
    document.cookie = "sidebar_collapsed=" + (collapsed ? "1" : "0") + "; path=/; max-age=31536000; samesite=lax";
    sidebarLinks().forEach(function(link) {
        var tooltip = bootstrap.Tooltip.getInstance(link);
        if (tooltip) tooltip.dispose();
    });
});

["mouseover", "focusin"].forEach(function(type) {
    document.addEventListener(type, function(event) {
        // After a swap the focus can land on the document itself.
        if (!(event.target instanceof Element)) return;
        var link = event.target.closest("#workshop-sidebar.is-collapsed .nav-link");
        if (!link || bootstrap.Tooltip.getInstance(link)) return;
        var label = link.querySelector(".nav-label");
        if (!label) return;
        bootstrap.Tooltip.getOrCreateInstance(link, {
            title: label.textContent.trim(),
            placement: "right",
            trigger: "hover focus",
        }).show();
    });
});

let expandAll = document.getElementById('expand-all');
if (expandAll) {
    document.getElementById('expand-all').onclick = function(){
        //click me function!
        console.log(this.getAttribute('aria-expanded'));
        this.setAttribute('aria-expanded', this.getAttribute('aria-expanded') !== 'true');
        this.classList.toggle('show');
        var addShow = false;
        if (this.classList.contains('show')) {
            addShow = true;
        }
        let children = document.querySelectorAll('.collapse');
        // console.log(children);
        children.forEach((c)=>{
            if (addShow) {
                c.classList.add('show');
                document.querySelector('[data-bs-target="#' + c.id + '"]').setAttribute('aria-expanded', true);
            } else {
                c.classList.remove('show');
                document.querySelector('[data-bs-target="#' + c.id + '"]').setAttribute('aria-expanded', false);
            }
        })
    }

}

$('header .shopping-basket a').click(function(e) {
    var modalEl = document.querySelector('.modal-checkout');
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
})

function setTotalPrice(modal) {
    var totalBasketPrice = 0;
    modal.find('table tbody tr.product').each(function(){
        if ($(this).data('product-price')) {
            var quantity = parseInt(($(this).data('quantity')));
            totalBasketPrice += quantity * parseFloat($(this).data('product-price')).toFixed(2);
        }
    });
    if (totalBasketPrice > 0) {
        modal.find('.price').removeClass('d-none');
        modal.find('.price').addClass('table-row');
        modal.find('.price-total span').html(totalBasketPrice.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 }));
    } else {
        modal.find('.price').addClass('d-none');
        modal.find('.price').removeClass('table-row');
        modal.find('.price-total span').html();
    }
    console.log('TOTAL BASKET PRICE: ', totalBasketPrice);
}



function setTotalBasketQuantity(modal) {
    var basket = $('#basket');
    var totalBasketQuantity = 0;
    $('.product-card .product-quantity').each(function(){
        var quantity = parseInt($(this).val());
        totalBasketQuantity += quantity;
    });
    console.log('TOTAL BASKET QTY:', totalBasketQuantity);
    if (totalBasketQuantity === 1) {
        basket.find('.single').removeClass('d-none').show();
        basket.find('.plural').hide();
        basket.find('.empty').hide();
        basket.find('.current-order').hide();

    } else if (totalBasketQuantity > 1) {
        basket.find('.plural').removeClass('d-none').show();
        basket.find('.single').hide();
        basket.find('.empty').hide();
        basket.find('.plural .qty').html(totalBasketQuantity);
        basket.find('.current-order').hide();
    }
    if (totalBasketQuantity == 0) {
        // $('header .shopping-basket').hide();
        // $('header .shopping-basket .order-quantity').show().html(totalBasketQuantity);
        $('header .shopping-basket .order-quantity').hide();
        basket.find('.summary').hide();
        if (basket.hasClass('has-order')) {
            basket.find('.current-order').show();
        } else {
            basket.find('.empty').removeClass('d-none').show();
        }
        // modal.find('form .form-check.terms-conditions').removeClass('d-none').hide();
        // modal.find('form button[type="submit"]').removeClass('d-none').hide();
        // modal.find('form button[data-bs-dismiss="modal"]').show();
        // modal.find('.modal-title span').removeClass('d-none').hide();
        // modal.find('form input[type="reset"]').removeClass('d-none').hide();
    } else {
        basket.find('.summary').removeClass('d-none').show();
        basket.find('.empty').hide();
        if (totalBasketQuantity > 0) {
            $('header .shopping-basket .order-quantity').removeClass('d-none');
            $('header .shopping-basket .order-quantity').show().html(totalBasketQuantity);
        }
        // // modal.find("form").dirty("setAsDirty");
        // modal.find("form .form-check.terms-conditions").removeClass('d-none').show();
        // modal.find('form .form-check.terms-conditions input').attr("required", true);
        // modal.find('form button[type="submit"]').removeClass('d-none').show();
        // modal.find('form button[data-bs-dismiss="modal"]').hide();
        // modal.find('.modal-title span').removeClass('d-none').show();
        // modal.find('form input[type="reset"]').removeClass('d-none').show();
        // modal.find('.text-cancel').hide();
        // modal.find('.text-change').show();
    }
}

function updateModalChange(modal){
    var form = modal.find('form');
    console.log('changed');
    form.find('.form-check.terms-conditions').removeClass('d-none').show();
    form.find('input[type="reset"]').removeClass('d-none').show();
    form.find('button.btn-update').removeClass('d-none').show();
    form.find('button.btn-cancel').removeClass('d-none').hide();
    form.find('a[data-bs-dismiss="modal"]').hide();
    modal.find('.modal-title span').removeClass('d-none').show();
    form.find('table').show();
    form.find('.message-empty-checkout').addClass('d-none').hide();
}
function updateModalUnchange(modal){
    var form = modal.find('form');
    console.log('unchanged');
    form.find('.form-check.terms-conditions').removeClass('d-none').hide();
    form.find('button.btn-update').removeClass('d-none').hide();
    form.find('button.btn-cancel').removeClass('d-none').hide();
    form.find('input[type="reset"]').removeClass('d-none').hide();
    form.find('a[data-bs-dismiss="modal"]').show();
    modal.find('.modal-title span').removeClass('d-none').hide();
}
function updateModalStorno(modal) {
    console.log('storno');
    var form = modal.find('form');
    form.find('.form-check.terms-conditions').removeClass('d-none').hide();
    form.find('.form-check.terms-conditions input').attr("required", false);
    form.find('button.btn-update').removeClass('d-none').hide();
    form.find('button.btn-cancel').removeClass('d-none').show();
    form.find('a[data-bs-dismiss="modal"]').hide();
    form.find('table').hide();
    form.find('.message-empty-checkout').removeClass('d-none').show();
}
function updateModalEmpty(modal) {
    console.log('empty');
    var form = modal.find('form');
    form.find('.form-check.terms-conditions').removeClass('d-none').hide();
    // form.find('.form-check.terms-conditions input').attr("required", false);
    form.find('table').hide();
    form.find('.message-empty-checkout').removeClass('d-none').show();
    form.find('a[data-bs-dismiss="modal"]').removeClass('d-none').show();
    form.find('button.btn-update').removeClass('d-none').hide();
    form.find('button.btn-cancel').removeClass('d-none').hide();
}

function updateModal(modal, basketQuantity, totalQuantity) {
    var form = modal.find('form');
    console.log('updateModal', basketQuantity, totalQuantity);
    if (basketQuantity === 0) {
        updateModalUnchange(modal);
    } else {
        updateModalChange(modal);
    }
    if (totalQuantity ===0) {
        if (form.hasClass('has_order')) {
            updateModalStorno(modal);
        } else {
            updateModalEmpty(modal);
        }
    }
}

function updateProduct(modal, product, qty, maintainOrderedQty) {
    qty = parseInt(qty);
    console.log('Update product', product, qty, maintainOrderedQty);
    // basket.find('.summary').removeClass('d-none');
    // basket.find('.current-order').hide();
    var row = modal.find("tr[data-product='" + product + "']");
    var orderedQuantity = row.data('ordered-quantity');
    // set current product basket qty
    row.data('basket-quantity', Math.max(0, qty));
    if (maintainOrderedQty) {
        qty = orderedQuantity + qty;
    }
    row.data('quantity', qty);
    row.find('select.order-quantity').val(qty);
    console.log('qty', qty > 0);
    if (qty > 0) {
        row.css('display', '');
        row.removeClass('d-none');
        row.addClass('table-row');
        console.log('show row');
    }
    //  else if (qty == 0) {
    //     row.addClass('d-none');
    //     row.removeClass('table-row');
    // }
    var productPrice = row.data('product-price');
    if (productPrice) {
        productPrice = parseFloat(productPrice);
        productPrice = qty * productPrice;
        // productPrice = parseFloat((+productPrice).toFixed(2));
        if (productPrice > 0 ) {
            row.find('.sale-price').removeClass('d-none').find('.price').html(productPrice.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 }));
        } else {
            row.find('.sale-price').addClass('d-none');
        }
    }
    // basket.removeClass('d-none');
}

$(document).on('keyup', 'input.product-quantity', function() {
    var _this = $(this);
    var min = parseInt(_this.attr('min')) || 1; // if min attribute is not defined, 1 is default
    var max = parseInt(_this.attr('max')) || 100; // if max attribute is not defined, 100 is default
    var val = parseInt(_this.val()) || (min - 1); // if input char is not a number the value will be (min - 1) so first condition will be true
    if (val < min)
        val = min
    if (val > max)
        val = max
    _this.val(val);
    // var product = _this.data('product');
    // updateProduct(product, val, true);
    var modal = $('.modal-checkout');
    setTotalBasketQuantity(modal);
    // setTotalPrice(modal);
});

let plus_btns = document.querySelectorAll('.input-group .btn-plus');
let minus_btns = document.querySelectorAll('.input-group .btn-minus');
let qty_inputs = document.querySelectorAll('.input-group input[type=number]');
   plus_btns.forEach(btn=>{
    console.log(btn.disabled)
    if (!btn.previousElementSibling.disabled){
        btn.addEventListener('click', ()=>{
            var value = (btn.previousElementSibling.value == btn.previousElementSibling.max) ? btn.previousElementSibling.max : parseInt(btn.previousElementSibling.value) + 1;
            btn.previousElementSibling.value = value
            // var product = btn.getAttribute('data-product');
            // updateProduct(product, value, true);
            var modal = $('.modal-checkout');
            setTotalBasketQuantity(modal);
            // setTotalPrice(modal);
        })
    }
})
minus_btns.forEach(btn=>{
    if (!btn.nextElementSibling.disabled) {
        btn.addEventListener('click', ()=>{
            var value = (btn.nextElementSibling.value == 0) ? 0 : btn.nextElementSibling.value - 1;
            btn.nextElementSibling.value = value;
            // var product = btn.getAttribute('data-product');
            // updateProduct(product, value, true);
            var modal = $('.modal-checkout');
            setTotalBasketQuantity(modal);
            // setTotalPrice(modal);
            })
        }
    })

$('.modal-checkout .btn-delete, .modal-abo .btn-delete').click(function(){
    var tr = $(this).parents('tr');
    tr.hide();
    tr.find('.order-quantity').val(0).change();
})
$('.modal-checkout form, .modal-abo form').on('reset', function(e)
{
    console.log('reset');
    var form = $(this);
    setTimeout(function() {
        console.log(form.find('tbody tr.product select'));
        $(this).parents('.modal').find('.modal-title span').hide();
        form.find('tbody tr.product select').change();
        form.find('.form-check.terms-conditions').removeClass('d-none').hide();
        form.find('button[type="submit"]').removeClass('d-none').hide();
        form.find('input[type="reset"]').removeClass('d-none').hide();
        form.find('a[data-bs-dismiss="modal"]').show();
        form.dirty("setAsClean");
        form.find('table').show();
        form.find('.message-empty-checkout').addClass('d-none').hide();
        form.find('.message-abo-orders').addClass('d-none');
        updatePosHint(form.find('.pos-select'));
        // The dropdown over the select shows the value the reset brought back.
        form.find('.pos-select').trigger('pos-dropdown-update');

        // var basket = $('#basket');
        // $('header .shopping-basket .order-quantity').hide();
        // var modal = form.parents('.modal-checkout');
        // $('.product-card .product-quantity').val(0);
        // setTotalBasketQuantity(modal);
        // basket.find('.summary').hide();
        // basket.find('.empty').show();
        // basket.find('.current-order').show();
     });
});

// The pick-up location has to be chosen when the usual one isn't offered on
// that production day, the hint stays as a note once that is done.
function updatePosHint(select) {
    var missing = select.prop('required') && !select.val();
    select.toggleClass('border-danger', missing);
    select.closest('form').find('.pos-hint').toggleClass('text-danger', missing).toggleClass('text-muted', !missing);
}
$('.pos-select').on('invalid', function() {
    this.setCustomValidity($(this).data('required-message') || '');
}).on('change', function() {
    this.setCustomValidity('');
    updatePosHint($(this));
});

// A dropdown over the select of the pick-up locations whose options show the
// address and pick-up times of each one: in the sign-up and profile forms
// (PointOfSaleSelect in users/forms.py) and in the checkout (checkout.html).
// The select stays in the form and holds the value.
function initPosDropdown(select) {
    function content(option) {
        var fragment = $('<span class="pos-dropdown-option"></span>');
        fragment.append($('<span class="pos-dropdown-name"></span>').text(option.text()));
        ['address', 'pickupTimes'].forEach(function(key) {
            if (option.data(key)) {
                fragment.append($('<small class="d-block text-muted"></small>').text(option.data(key)));
            }
        });
        return fragment;
    }
    var inline = select.hasClass('d-inline');
    var toggle = $('<button type="button" class="form-select text-start pos-dropdown-toggle" data-bs-toggle="dropdown" aria-haspopup="listbox" aria-expanded="false"></button>');
    var menu = $('<ul class="dropdown-menu shadow" role="listbox"></ul>');
    select.find('option').each(function() {
        var option = $(this);
        // The placeholder of the checkout ("Please choose …") is no choice.
        if (option.prop('disabled') || option.val() === '') {
            return;
        }
        var item = $('<button type="button" class="dropdown-item" role="option"></button>').append(content(option));
        item.data('value', option.val()).on('click', function() {
            select.val(option.val()).trigger('change');
        });
        menu.append($('<li></li>').append(item));
    });
    function update() {
        // Closed it is one line with the name, as a select; the details are in
        // the options of the open dropdown.
        toggle.text(select.find('option:selected').text());
        toggle.prop('disabled', select.prop('disabled'));
        toggle.toggleClass('is-invalid', select.hasClass('is-invalid') || select.hasClass('border-danger'));
        menu.find('.dropdown-item').each(function() {
            var chosen = String($(this).data('value')) === String(select.val());
            $(this).toggleClass('active', chosen).attr('aria-selected', chosen ? 'true' : 'false');
        });
    }
    update();
    select.on('change pos-dropdown-update', update);
    // A hidden select can't show the browser's message for a missing choice:
    // the dropdown is marked and focused instead, the hint below says why.
    select.on('invalid', function(event) {
        event.preventDefault();
        toggle.addClass('is-invalid').trigger('focus');
    });
    toggle.attr('aria-labelledby', $('label[for="' + select.attr('id') + '"]').attr('id') || null);
    toggle.toggleClass('form-select-xs', select.hasClass('form-select-xs'));
    var dropdown = $('<div class="dropdown pos-dropdown"></div>').toggleClass('pos-dropdown-inline', inline);
    select.addClass('d-none').removeClass('d-inline').after(dropdown.append(toggle, menu));
}
$(function() {
    $('select[data-pos-dropdown]').each(function() {
        initPosDropdown($(this));
    });
});

var aboProductDays = {};
$(function(){
    $('.link-new-tab a').attr('target', '_blank');
    $('.link-new-tab a').attr('rel', 'nofollow noopener');
    $('.modal-checkout, .modal-abo').on('hide.bs.modal', function() {
        // // console.log('hide', $('.modal-checkout form input[type="reset"]'));
        $(this).find('form input[type="reset"]').click();
    })
    $('.modal-checkout').on('show.bs.modal', function() {
        var modal = $(this);
        if ($(this).hasClass('in-checkout')) {
            var basketQuantity = 0;
            var totalBasketQuantity = 0;
            $('.product-card').each(function(){
                var product = $(this).data('product');
                var orderedQty = $(this).data('ordered-quantity');
                var quantity = parseInt($(this).find('.product-quantity').val()) || 0;
                totalBasketQuantity = totalBasketQuantity + orderedQty + quantity;
                basketQuantity += basketQuantity + quantity;
                console.log(product, quantity);
                updateProduct(modal, product, quantity, true);
                // totalBasketQuantity += quantity;
            });
            setTotalPrice(modal);
            console.log('basketQuantity', basketQuantity);
            console.log('totalBasketQuantity', totalBasketQuantity);
            updateModal(modal, basketQuantity, totalBasketQuantity);
        }
        var productionDay = modal.data('production-day');
        // TODO should not be a fix url
        $.get('/shop/api/production-day-abo-products/' + productionDay + '/' ,function(data, status){
            aboProductDays = data;
        });
    })
    if ($('.modal-checkout.in-checkout').length) {
        console.log('checkout exists');
        $('header .shopping-basket').addClass('d-lg-block');
    }
    // } else {
    //     console.log('checkout not');
    //     $('header .shopping-basket').removeClass('d-lg-block');
    // }
    var initdata = $('.modal-checkout form').serialize();

    $('.modal-checkout form select').change(function(){
        // console.log('form select change');
        // var basketQty = this.value;
        // // set number input of product card
        // var orderedQty = $(this).parents('tr').data('ordered-quantity');
        // if (orderedQty) {
        //     console.log('detect qty select change to set total basket qty');
        //     var qty = Math.max(basketQty - orderedQty, 0);
        //     $(this).parents('tr').data('basket-quantity', qty);
        //     var basket = $('#basket');
        //     var modal = $(this).parents('.modal-checkout');
        //     setTotalBasketQuantity(modal, basket);
        //     // $('input[data-product=' + $(this).parents('tr').data('product') + ']').val(qty);
        // } else {
        //     $('input[data-product=' + $(this).parents('tr').data('product') + ']').val(basketQty);
        // }
    })
    $('.modal-abo form select.order-quantity').change(function(){
        // quantity changes in the abo modal
        console.log('detect abo modal form change');
        var form = $(this).parents('form');
        var modal = $(this).parents('.modal');
        var product = $(this).parents('tr').data('product');
        console.log($(this).val());
        var qty = this.value;
        updateProduct(modal, product, qty, false);
        var basketQuantity = 0;
        form.find('tr.product select').each(function(){
            var qty = parseInt($(this).val());
            basketQuantity = basketQuantity + qty;
        })
        if (basketQuantity === 0) {
            updateModalStorno(modal);
        } else if (form.dirty('isDirty')) {
            updateModalChange(modal);
        } else {
            updateModalUnchange(modal);
        }
    })
    $('.modal-checkout form tr.product .abo-checkbox, .modal-checkout form tr.product select.order-quantity').change(function(){
        // show info message about created abo orders
        var form = $(this).parents('form');
        var currentAboProductDays = [];
        console.log("aboProductDays", aboProductDays);
        form.find('tr.product .abo-checkbox:checked').each(function(){
            var product = $(this).attr('name').replace('productabo-', '');
            var selectedQty = parseInt($(this).parents('tr.product').find('select.order-quantity').val());
            if (aboProductDays[product]) {
                for (const [key, value] of Object.entries(aboProductDays[product])) {
                    // console.log(value - selectedQty);
                    if (value - selectedQty >= 0){
                        currentAboProductDays.push(key)
                    }
                  }
            }
        })
        // console.log(aboProductDays);
        // console.log(currentAboProductDays);
        // currentAboProductDays = Object.keys(currentAboProductDays).filter((key) => currentAboProductDays[key] > 0)
        if (currentAboProductDays.length) {
            currentAboProductDays = Array.from(new Set(currentAboProductDays));
            currentAboProductDays.sort((a, b) => a - b);
            // console.log(currentAboProductDays);
            currentAboProductDays = currentAboProductDays.map((str) => {
                return new Date(str).toLocaleDateString('de-DE');
            });
            $('.alert.message-abo-orders').removeClass('d-none').find('span').html(currentAboProductDays.join(', '));
        } else {
            $('.alert.message-abo-orders').addClass('d-none');
        }

    });
    $('.modal-checkout form input, .modal-checkout form select.order-quantity, .modal-checkout form select.pos-select').change(function() {
        // Any changes in the checkout or order modal
        console.log('detect checkout/order modal form change');
        var form = $(this).parents('form');
        var modal = $(this).parents('.modal-checkout');
        var nowdata = form.serialize();
        // console.log(form, form.dirty('isClean'), form.dirty('isDirty'), form.dirty('showDirtyFields'));
        if ($(this).hasClass('order-quantity')) {
            var product = $(this).parents('tr').data('product');
            var qty = this.value;
            var modal = $(this).parents('.modal-checkout');
            if (modal.hasClass('in-checkout')) {
                // only maintain ordered qty if we are in a real checkout and not just updating an order
                var orderedQty = $(this).parents('tr').data('ordered-quantity');
                if (orderedQty) {
                    qty = qty - orderedQty;
                }
                updateProduct(modal, product, qty, true);
            } else {
                updateProduct(modal, product, qty, false);
            }
            setTotalPrice(modal);
        }
        var basketQuantity = 0;
        var totalBasketQuantity = 0;
        form.find('tr.product select').each(function(){
            var orderedQty = $(this).parents('tr').data('ordered-quantity');
            var qty = parseInt($(this).val());
            totalBasketQuantity = totalBasketQuantity + qty;
            basketQuantity = basketQuantity + (orderedQty - qty);
        })
        if (totalBasketQuantity === 0) {
            if (form.hasClass('has_order')) {
                updateModalStorno(modal);
            } else {
                updateModalEmpty(modal);
            }
        } else if (basketQuantity > 0 ){
            updateModalChange(modal);
        } else if (form.dirty('isDirty')) {
            updateModalChange(modal);
        } else {
            updateModalUnchange(modal);
        }
    });
    $('.product-card .figure.has-video img').click(function(){
        var figure = $(this).parents('.figure');
        var play_button = $(figure).find('.fa-circle-play');
        var video = $(figure).find('.video-container');
        var mute_btn = $(figure).find('.btn-mute');

        if (video.length) {
            mute_btn.show();
            $(figure).find('.product-tags').hide();
            video.css('height',figure.outerHeight() + "px");
            video.show();
            var video_element = video.find('video').get(0);
            video_element.play();
            $(figure).find('img').hide();
            video_element.addEventListener('play', function() {
                $(this).find('.fa-circle-play').hide();
            });

            // Event listener for 'pause' to show the button
            video_element.addEventListener('pause', function() {
                play_button.show();
            });
            // Event listener for 'ended' to show the button
            video_element.addEventListener('ended', function() {
                play_button.show();
                $(figure).find('img').show();
                $(figure).find('.product-tags').show();
                video.hide();
            });

            // Initial icon setup to play or pause
            video_element.addEventListener('playing', () => {
                play_button.hide();
            });
            $(video_element).add(play_button).click(function() {
                if (video_element.paused) {
                    video_element.play();
                    play_button.hide();
                } else {
                    video_element.pause();
                    play_button.show();
                }
            });
            $(figure).find('.btn-mute').click(function() {
                video_element.muted = !video_element.muted;
                if (video_element.muted) {
                    mute_btn.find('.fa-volume-xmark').show();
                    mute_btn.find('.fa-volume-high').hide();
                } else {
                    mute_btn.find('.fa-volume-xmark').hide();
                    mute_btn.find('.fa-volume-high').show();
                }
            })
        }
    });
});



var navbar = document.getElementById('navbar');
if(navbar && !navbar.classList.contains('nav-bg-dark')) {
    window.onscroll = function () {
        if (document.body.scrollTop >= 200 || document.documentElement.scrollTop >= 200 ) {
            navbar.classList.add("nav-bg-dark");
        }
        else {
            navbar.classList.remove("nav-bg-dark");
        }
    };
}
const myCollapsible = document.getElementById('navbarSupportedContent')
const header = document.querySelector('header');
if (myCollapsible) {
    myCollapsible.addEventListener('show.bs.collapse', event => {
        navbar.classList.add("nav-bg-dark");
        header.classList.add("open");
        document.body.classList.add("position-fixed-mobile");
    })
    myCollapsible.addEventListener('hidden.bs.collapse', event => {
        header.classList.remove("open");
        document.body.classList.remove("position-fixed-mobile");
        if (document.body.scrollTop >= 200 || document.documentElement.scrollTop >= 200 ) {
        } else {
            navbar.classList.remove("nav-bg-dark");
        }

    })
}
$(function() {
    // open external links and documents in a new tab
    $('a[href^="http"], a[href^="/documents/"]').attr({'target': '_blank', 'rel': 'nofollow noopener'});
    $('a[href^="/documents/"]').attr({'target': '_blank'});

    $('#id_message').change(function(){
        this.closest('form').submit();
    });
    var offset = 77;
    if ($('#basket').length) {
        var boxInitialTop = $('#basket').offset().top;
        // var width = $('.sticky').width();
        // console.log('width: ', width);
        $(window).scroll(function () {
          if ($(window).scrollTop() > boxInitialTop - offset) {
            $('header .shopping-basket').removeClass('invisible');
            // $('.sticky').addClass('sticked').css({position: 'fixed', top: offset + 'px', width: width + 'px'})
        } else {
              $('header .shopping-basket').addClass('invisible');
            // $('.sticky').removeClass('sticked').css({position: 'static', width: 'auto'});
          }
        });
    }
});

var openRecipeCollapses = [];
var amountSaved = {};
var amountSent = {};
var amountInflight = {};

function amountInput(form) {
    return form.querySelector("input[name=amount]");
}

function refreshAmountForms() {
    document.querySelectorAll(".amount-form").forEach(function(form) {
        var input = amountInput(form);
        if (!(input.id in amountSaved)) amountSaved[input.id] = input.value;
        var busy = amountInflight[form.id] > 0;
        input.classList.toggle("border-warning", input.value !== amountSaved[input.id]);
        form.querySelector(".amount-unit").classList.toggle("d-none", busy);
        form.querySelector(".amount-spinner").classList.toggle("d-none", !busy);
    });
}

function amountFormsDirty() {
    return [].some.call(document.querySelectorAll(".amount-form"), function(form) {
        return amountInflight[form.id] > 0 || amountInput(form).value !== amountSaved[amountInput(form).id];
    });
}

document.addEventListener("DOMContentLoaded", refreshAmountForms);
document.addEventListener("input", function(event) {
    if (event.target.closest(".amount-form")) refreshAmountForms();
});
document.addEventListener("htmx:config:request", function(event) {
    var form = event.target.closest(".amount-form");
    if (!form) return;
    var input = amountInput(form);
    var sourceEvent = event.detail.ctx.sourceEvent;
    var trigger = sourceEvent ? sourceEvent.type : "";
    var unchanged = input.value === amountSaved[input.id] || (amountInflight[form.id] > 0 && input.value === amountSent[form.id]);
    if (!input.checkValidity()) {
        if (trigger !== "input") input.reportValidity();
        event.preventDefault();
        return;
    }
    if (unchanged && trigger !== "submit") event.preventDefault();
});
document.addEventListener("htmx:before:request", function(event) {
    var form = event.target.closest(".amount-form");
    if (!form) return;
    var input = amountInput(form);
    event.detail.ctx.amountCounted = true;
    amountSent[form.id] = input.value;
    amountInflight[form.id] = (amountInflight[form.id] || 0) + 1;
    refreshAmountForms();
});
document.addEventListener("htmx:finally:request", function(event) {
    // A request that swapped its own element out ends on the document.
    if (!(event.target instanceof Element)) return;
    var form = event.target.closest(".amount-form");
    if (!form || !event.detail.ctx.amountCounted) return;
    amountInflight[form.id] -= 1;
    refreshAmountForms();
});
function isRecipeSwap(event) {
    return event.target.closest("#recipe-figures");
}

document.addEventListener("htmx:before:swap", function(event) {
    if (!isRecipeSwap(event)) return;
    openRecipeCollapses = [].map.call(document.querySelectorAll("#recipe-figures .collapse.show"), function(el) {
        return el.id;
    });
});
document.addEventListener("htmx:after:swap", function(event) {
    if (!isRecipeSwap(event)) return;
    openRecipeCollapses.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.classList.add("show");
    });
    showMessages();
    var failed = document.querySelector("#messages .toast");
    if (event.target.id === "add-ingredient-form" && !failed) resetAddIngredient();
    var form = event.target.closest(".amount-form");
    document.querySelectorAll(".amount-form input[name=amount]").forEach(function(other) {
        if (other !== document.activeElement && (!form || other !== amountInput(form))) {
            amountSaved[other.id] = other.value;
        }
    });
    if (!form) {
        refreshAmountForms();
        return;
    }
    var input = amountInput(form);
    if (!failed) amountSaved[input.id] = amountSent[form.id];
    refreshAmountForms();
    if (!failed && input.value === amountSaved[input.id]) {
        input.classList.add("is-valid");
        setTimeout(function() { input.classList.remove("is-valid"); }, 1500);
    }
});
document.addEventListener("keydown", function(event) {
    if (event.key !== "Tab" || !event.target.closest(".amount-form")) return;
    var inputs = [].filter.call(document.querySelectorAll(".amount-form input[name=amount], #add-ingredient-weight"), function(input) {
        return input.offsetParent !== null && !input.disabled;
    });
    var next = inputs[inputs.indexOf(event.target) + (event.shiftKey ? -1 : 1)];
    if (!next) return;
    event.preventDefault();
    next.focus();
    next.select();
});
$(document).on("select2:open", function() {
    setTimeout(function() {
        var search = document.querySelector(".select2-container--open .select2-search__field");
        if (search) search.focus();
    }, 0);
});

var addIngredientForm = document.getElementById("add-ingredient-form");

function addIngredientSelect() {
    return $("#id_ingredient");
}

function toggleNewIngredient(isNew) {
    addIngredientForm.querySelector(".add-ingredient-new").classList.toggle("d-none", !isNew);
}

function resetAddIngredient() {
    addIngredientForm.reset();
    addIngredientSelect().val(null).trigger("change");
    toggleNewIngredient(false);
    document.getElementById("add-ingredient-weight").focus();
}

if (addIngredientForm) {
    var addIngredientWeight = document.getElementById("add-ingredient-weight");
    $(document).on("select2:select", "#id_ingredient", function(event) {
        var isNew = String(event.params.data.id).indexOf("new:") === 0;
        toggleNewIngredient(isNew);
        if (isNew) {
            addIngredientForm.querySelector("select[name=category]").focus();
        } else if (addIngredientWeight.value && addIngredientWeight.checkValidity()) {
            addIngredientForm.requestSubmit();
        } else {
            addIngredientWeight.focus();
        }
    });
    $(document).on("select2:clear select2:unselect", "#id_ingredient", function() {
        toggleNewIngredient(false);
    });
    addIngredientWeight.addEventListener("keydown", function(event) {
        if (event.key !== "Tab" || event.shiftKey) return;
        event.preventDefault();
        addIngredientSelect().select2("open");
    });
}
document.addEventListener("htmx:config:request", function(event) {
    if (event.target.id !== "add-ingredient-form") return;
    var weight = document.getElementById("add-ingredient-weight");
    if (!weight.value || !weight.checkValidity()) {
        weight.reportValidity();
        event.preventDefault();
    } else if (!addIngredientSelect().val()) {
        event.preventDefault();
        addIngredientSelect().select2("open");
    }
});
var recipeFigures = document.getElementById("recipe-figures");

function closePercentRow(row) {
    if (row) row.classList.remove("row-percent");
}

function initRecipePopovers() {
    document.querySelectorAll('#recipe-figures [data-bs-toggle="popover"]').forEach(function(el) {
        var popover = bootstrap.Popover.getInstance(el);
        if (popover && el.getAttribute("title")) {
            popover.dispose();
            popover = null;
        }
        if (!popover) new bootstrap.Popover(el);
    });
}

if (recipeFigures) {
    document.addEventListener("click", function(event) {
        var button = event.target.closest(".percent-edit");
        if (!button) return;
        var input = document.getElementById("percent-" + button.dataset.row);
        if (!input || input.disabled) return;
        if (!document.getElementById("recipe-figures").classList.contains("unit-percent")) {
            document.getElementById("row-" + button.dataset.row).classList.add("row-percent");
        }
        input.focus();
        input.select();
    });
    document.addEventListener("focusout", function(event) {
        if (!event.target.closest(".row-percent form.unit-percent-only")) return;
        closePercentRow(event.target.closest(".row-percent"));
    });
    document.addEventListener("keydown", function(event) {
        if (event.key !== "Escape") return;
        var row = event.target.closest(".row-percent");
        if (!row) return;
        event.target.value = amountSaved[event.target.id];
        refreshAmountForms();
        closePercentRow(row);
    });
    document.addEventListener("htmx:before:swap", function(event) {
        if (!isRecipeSwap(event)) return;
        document.querySelectorAll('#recipe-figures [data-bs-toggle="popover"]').forEach(function(el) {
            var popover = bootstrap.Popover.getInstance(el);
            if (popover) popover.hide();
        });
    });
    document.addEventListener("htmx:after:swap", function(event) {
        if (isRecipeSwap(event)) initRecipePopovers();
    });
}
var ingredientOrder = [];

function rootRowIds() {
    return [].map.call(document.querySelectorAll('#recipe-figures li[id^="row-"]'), function(row) {
        return row.id;
    });
}

document.addEventListener("htmx:before:swap", function(event) {
    if (event.target.id === "sort-ingredients") ingredientOrder = rootRowIds();
});
document.addEventListener("htmx:after:swap", function(event) {
    if (event.target.id !== "sort-ingredients") return;
    rootRowIds().forEach(function(id, index) {
        if (ingredientOrder[index] === id) return;
        var row = document.getElementById(id);
        row.classList.add("bg-warning", "bg-opacity-25");
        setTimeout(function() { row.classList.remove("bg-warning", "bg-opacity-25"); }, 1200);
    });
});

document.addEventListener("keydown", function(event) {
    if (!event.target.matches(".instructions-input, .note-input")) return;
    var form = event.target.closest("form");
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        form.requestSubmit();
    } else if (event.key === "Escape") {
        var cancel = form.querySelector(".instructions-cancel, .note-cancel");
        if (!cancel) return;
        event.preventDefault();
        cancel.click();
    }
});

// Buttons with data-confirm-tap need a second tap within three seconds, a
// first tap only arms them. Works for touch screens where a confirm dialog
// is in the way.
var armedTap = null;
var armedTapTimeout = null;

function disarmTap() {
    if (!armedTap) return;
    armedTap.classList.remove("is-armed");
    armedTap = null;
    clearTimeout(armedTapTimeout);
}

document.addEventListener("click", function(event) {
    var button = event.target.closest("[data-confirm-tap]");
    if (button === armedTap && button) {
        disarmTap();
        return;
    }
    disarmTap();
    if (!button) return;
    event.preventDefault();
    armedTap = button;
    button.classList.add("is-armed");
    armedTapTimeout = setTimeout(disarmTap, 3000);
});

var armedDelete = null;
var armedDeleteTimeout = null;

function disarmDelete() {
    if (!armedDelete) return;
    armedDelete.classList.replace("btn-danger", "btn-outline-primary");
    armedDelete.querySelector(".delete-label").classList.remove("d-sm-inline");
    armedDelete = null;
    clearTimeout(armedDeleteTimeout);
}

document.addEventListener("click", function(event) {
    var link = event.target.closest(".delete-link");
    if (link !== armedDelete) disarmDelete();
    if (!link || !window.htmx) return;
    event.preventDefault();
    if (!armedDelete) {
        armedDelete = link;
        link.classList.replace("btn-outline-primary", "btn-danger");
        link.querySelector(".delete-label").classList.add("d-sm-inline");
        armedDeleteTimeout = setTimeout(disarmDelete, 3000);
        return;
    }
    disarmDelete();
    var row = link.closest(".list-group-item");
    row.style.transition = "opacity 200ms";
    row.style.opacity = "0.3";
    htmx.ajax("POST", link.getAttribute("href"), {
        source: "#recipe-figures",
        target: "#recipe-figures",
        select: "#recipe-figures",
        selectOOB: "#messages",
        swap: "outerMorph",
        headers: {"X-CSRFToken": link.dataset.csrf},
    });
});
document.addEventListener("keydown", function(event) {
    if (event.key === "Escape") disarmDelete();
});
window.addEventListener("beforeunload", function(event) {
    if (amountFormsDirty()) {
        event.preventDefault();
        event.returnValue = "";
    }
});

// Production plan: cards start collapsed, remember which ones were opened,
// per browser.
var expandedCardsKey = "production-plan-expanded";

function getExpandedCards() {
    try {
        return JSON.parse(localStorage.getItem(expandedCardsKey)) || [];
    } catch (error) {
        return [];
    }
}

function setExpandedCards(ids) {
    try {
        localStorage.setItem(expandedCardsKey, JSON.stringify(ids.slice(-200)));
    } catch (error) {}
}

function restoreExpandedCards() {
    getExpandedCards().forEach(function(id) {
        var body = document.getElementById(id);
        if (!body || !body.closest(".production-card")) return;
        body.classList.add("show");
        var toggle = document.querySelector('[data-bs-target="#' + id + '"]');
        if (toggle) toggle.setAttribute("aria-expanded", "true");
    });
}

document.addEventListener("DOMContentLoaded", restoreExpandedCards);
document.addEventListener("htmx:after:swap", restoreExpandedCards);

// A link to a card, e.g. the plan button on the production day, opens it and
// remembers it as open, so it stays open after the next swap.
function openLinkedCard() {
    var id = location.hash.slice(1);
    var card = id && document.getElementById(id);
    if (!card || !card.classList.contains("production-card")) return;
    var body = document.getElementById(id + "-body");
    if (body && body.classList.contains("collapse")) {
        body.classList.add("show");
        var toggle = document.querySelector('[data-bs-target="#' + body.id + '"]');
        if (toggle) toggle.setAttribute("aria-expanded", "true");
        var ids = getExpandedCards().filter(function(other) { return other !== body.id; });
        ids.push(body.id);
        setExpandedCards(ids);
    }
    card.scrollIntoView({ block: "start" });
}

document.addEventListener("DOMContentLoaded", openLinkedCard);
window.addEventListener("hashchange", openLinkedCard);

// The server renders every card collapsed, a morph would close an open card
// until htmx:after:swap opens it again. htmx swaps asynchronously, so the
// browser may paint in between: the card flickers and the page jumps.
document.addEventListener("DOMContentLoaded", function() {
    if (!window.htmx) return;
    htmx.registerExtension("production-card-open", {
        htmx_before_morph_attr: function(el, detail) {
            if (detail.attrName === "class" && el.classList.contains("show") &&
                el.parentElement && el.parentElement.classList.contains("production-card") &&
                !/(^|\s)show(\s|$)/.test(detail.newValue)) {
                return false;
            }
            if (detail.attrName === "aria-expanded" && el.matches(".production-card-title") &&
                el.getAttribute("aria-expanded") === "true") {
                return false;
            }
        }
    });
});

// Production plan: the dough a baker chose to make next, per card and browser.
// A cookie, so the server marks the current dough, see get_chosen_steps.
var chosenStepsCookie = "production_steps";

function setChosenStep(card, step) {
    var steps = {};
    var match = document.cookie.match(new RegExp("(?:^|; )" + chosenStepsCookie + "=([^;]*)"));
    try {
        if (match) steps = JSON.parse(decodeURIComponent(match[1]));
    } catch (error) {}
    steps[card] = step;
    // Numeric keys are in ascending order, the oldest plans go first.
    Object.keys(steps).slice(0, -50).forEach(function(key) { delete steps[key]; });
    document.cookie = chosenStepsCookie + "=" + encodeURIComponent(JSON.stringify(steps)) +
        "; path=/; max-age=2592000; SameSite=Lax";
}

document.addEventListener("htmx:config:request", function(event) {
    var button = event.target.closest && event.target.closest(".production-step-choose");
    if (button) setChosenStep(button.dataset.card, Number(button.dataset.step));
});

// Production plan: keep the card of a start, finish or cancel at its place
// on the screen. Content above it changes height with the swap, Safari doesn't
// anchor the scroll position like Chrome and Firefox do.
var swappedCard = null;

document.addEventListener("htmx:before:swap", function(event) {
    var card = event.target.closest && event.target.closest(".production-card");
    swappedCard = card ? {id: card.id, top: card.getBoundingClientRect().top} : null;
});
document.addEventListener("htmx:after:swap", function() {
    if (!swappedCard) return;
    var card = document.getElementById(swappedCard.id);
    if (card) window.scrollBy(0, card.getBoundingClientRect().top - swappedCard.top);
    swappedCard = null;
});
document.addEventListener("shown.bs.collapse", function(event) {
    var card = event.target.closest(".production-card");
    if (!card) return;
    var ids = getExpandedCards().filter(function(id) { return id !== event.target.id; });
    ids.push(event.target.id);
    setExpandedCards(ids);
    // A card the baker opened comes into view, if it doesn't fit already.
    var rect = card.getBoundingClientRect();
    if (rect.top < 0 || rect.bottom > window.innerHeight) {
        card.scrollIntoView({behavior: "smooth", block: "start"});
    }
});
document.addEventListener("hidden.bs.collapse", function(event) {
    if (!event.target.closest(".production-card")) return;
    setExpandedCards(getExpandedCards().filter(function(id) { return id !== event.target.id; }));
});

// Production plan: keep the screen of a tablet on while baking, with the
// Screen Wake Lock API (Safari on iPad from iPadOS 16.4).
var wakeLockKey = "production-plan-wake-lock";
var wakeLock = null;

function wakeLockWanted() {
    try {
        return localStorage.getItem(wakeLockKey) === "1";
    } catch (error) {
        return false;
    }
}

function renderWakeLockButton() {
    var button = document.getElementById("wake-lock-toggle");
    if (!button) return;
    if (!("wakeLock" in navigator)) return;
    button.classList.remove("d-none");
    button.classList.toggle("active", wakeLock !== null);
    button.setAttribute("aria-pressed", wakeLock !== null ? "true" : "false");
}

function requestWakeLock() {
    if (!("wakeLock" in navigator) || wakeLock || !document.getElementById("wake-lock-toggle")) {
        renderWakeLockButton();
        return;
    }
    navigator.wakeLock.request("screen").then(function(lock) {
        wakeLock = lock;
        lock.addEventListener("release", function() {
            wakeLock = null;
            renderWakeLockButton();
        });
        renderWakeLockButton();
    }).catch(function() {
        renderWakeLockButton();
    });
}

document.addEventListener("click", function(event) {
    var toggle = event.target.closest("#wake-lock-toggle");
    if (!toggle) return;
    toggle.blur();
    // Safari may refuse the lock without a tap, so a tap on an inactive
    // button always turns it on.
    var wanted = wakeLock === null;
    try {
        localStorage.setItem(wakeLockKey, wanted ? "1" : "0");
    } catch (error) {}
    if (wanted) {
        requestWakeLock();
    } else if (wakeLock) {
        wakeLock.release();
    }
});

function resumeWakeLock() {
    if (wakeLockWanted() && document.visibilityState === "visible") {
        requestWakeLock();
    } else {
        renderWakeLockButton();
    }
}

document.addEventListener("DOMContentLoaded", resumeWakeLock);
document.addEventListener("htmx:after:swap", resumeWakeLock);
// The lock is released when the tab is hidden, take it again on return.
document.addEventListener("visibilitychange", resumeWakeLock);

// Production plan: a finished dough is collapsed. Keep one open that the baker
// opened again, the next swap or sync would close it otherwise.
var openedDoneSteps = new Set();

document.addEventListener("toggle", function(event) {
    if (!event.target.matches || !event.target.matches(".production-step-collapsed")) return;
    var id = event.target.closest(".production-step").id;
    if (event.target.open) {
        openedDoneSteps.add(id);
    } else {
        openedDoneSteps.delete(id);
    }
}, true);

// Production plan: htmx swaps the cards, so their popovers are made on the
// first hover or focus. They go before a swap, an open one would stay behind.
["mouseover", "focusin"].forEach(function(type) {
    document.addEventListener(type, function(event) {
        // After a swap the focus can land on the document itself.
        if (!(event.target instanceof Element)) return;
        var el = event.target.closest('.production-card [data-bs-toggle="popover"]');
        if (!el || bootstrap.Popover.getInstance(el)) return;
        bootstrap.Popover.getOrCreateInstance(el).show();
    });
});
document.addEventListener("htmx:before:swap", function() {
    document.querySelectorAll('.production-card [data-bs-toggle="popover"]').forEach(function(el) {
        var popover = bootstrap.Popover.getInstance(el);
        if (popover) popover.dispose();
    });
});

document.addEventListener("htmx:after:swap", function() {
    openedDoneSteps.forEach(function(id) {
        var details = document.querySelector("#" + id + " > .production-step-collapsed");
        if (details) details.open = true;
    });
});

// Production day: the open tab is kept in the URL hash, so a reload, a
// redirect to "#orders" or switching the day with htmx shows the same tab.
function showDayTab(id) {
    var button = document.querySelector('.day-tabs [data-bs-target="#' + id + '"]');
    if (button) bootstrap.Tab.getOrCreateInstance(button).show();
}

var dayTab = location.hash.slice(1);

document.addEventListener("shown.bs.tab", function(event) {
    if (!event.target.closest(".day-tabs")) return;
    dayTab = event.target.getAttribute("data-bs-target").slice(1);
    history.replaceState(history.state, "", "#" + dayTab);
});
document.addEventListener("DOMContentLoaded", function() {
    if (dayTab) showDayTab(dayTab);
});
// A tab of the plan that leads to a pane of the day page: htmx swaps the
// page, the pane opens after the swap.
document.addEventListener("click", function(event) {
    var link = event.target.closest(".day-tabs [data-day-pane]");
    if (link) dayTab = link.dataset.dayPane;
});
function keepDayTab() {
    // Only a pane of the day page: the plan and the emails have the tab row
    // too, there the hash is something else, e.g. a card of the plan.
    if (!dayTab || !document.getElementById(dayTab + "-tab")) return;
    showDayTab(dayTab);
    if (location.hash !== "#" + dayTab) {
        history.replaceState(history.state, "", "#" + dayTab);
    }
}
document.addEventListener("htmx:after:swap", keepDayTab);
// htmx pushes the new URL without the hash.
document.addEventListener("htmx:after:history:push", keepDayTab);

document.addEventListener("click", function(event) {
    if (event.target.closest("[data-print]")) window.print();
});

// Pickup emails: the number of recipients follows the chosen point of sale,
// sending is off without any.
function updateRecipientCount() {
    var data = document.getElementById("recipient-counts");
    var select = document.getElementById("id_point_of_sale");
    if (!data || !select) return;
    var count = JSON.parse(data.textContent)[select.value] || 0;
    document.querySelectorAll("[data-recipient-count], #reminder-send [data-action-badge]").forEach(function(el) {
        el.textContent = count;
    });
    var send = document.getElementById("reminder-send");
    if (send) send.disabled = count === 0;
}

document.addEventListener("change", function(event) {
    if (event.target.id === "id_point_of_sale") updateRecipientCount();
});
document.addEventListener("DOMContentLoaded", updateRecipientCount);

// Pickup emails: a placeholder goes in at the cursor of the subject or the
// text, whichever was used last. The chips keep the focus where it is. The
// text gets it as a paste, which Draftail handles like any pasted text,
// typing it would confuse the editor in an empty line.
var placeholderField = null;

document.addEventListener("focusin", function(event) {
    if (!document.querySelector(".reminder-tags")) return;
    if (event.target.id === "id_subject" || event.target.closest(".DraftEditor-root")) {
        placeholderField = event.target;
    }
});
document.addEventListener("mousedown", function(event) {
    if (event.target.closest("[data-insert]")) event.preventDefault();
});
document.addEventListener("click", function(event) {
    var tag = event.target.closest("[data-insert]");
    if (!tag) return;
    var text = tag.dataset.insert;
    var field = placeholderField || document.querySelector(".reminder-editor [contenteditable=true]");
    if (!field) return;
    if (document.activeElement !== field) field.focus();
    if (field.setRangeText) {
        field.setRangeText(text, field.selectionStart, field.selectionEnd, "end");
        field.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
        var data = new DataTransfer();
        data.setData("text/plain", text);
        var paste = new Event("paste", { bubbles: true, cancelable: true });
        Object.defineProperty(paste, "clipboardData", { value: data });
        field.dispatchEvent(paste);
    }
    document.body.dispatchEvent(new Event("reminder-preview"));
});

// Delivery bill: the name filter hides the orders of other customers and the
// points of sale without a match. It runs again after a swap, e.g. when the
// orders of a point of sale are ticked as picked up.
function normalizeName(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
}
function filterDeliveryBills() {
    var input = document.getElementById("delivery-bill-filter");
    if (!input) return;
    var query = normalizeName(input.value);
    var matches = 0;
    document.querySelectorAll(".delivery-bill").forEach(function(section) {
        var sectionMatches = 0;
        section.querySelectorAll(".delivery-bill-order").forEach(function(row) {
            var isMatch = normalizeName(row.querySelector(".delivery-bill-name").textContent).includes(query);
            row.hidden = !isMatch;
            sectionMatches += isMatch ? 1 : 0;
        });
        section.hidden = query !== "" && sectionMatches === 0;
        section.querySelector(".delivery-bill-summary").hidden = query !== "";
        matches += sectionMatches;
    });
    document.getElementById("delivery-bill-filter-empty").hidden = query === "" || matches > 0;
}
document.addEventListener("input", function(event) {
    if (event.target.id === "delivery-bill-filter") filterDeliveryBills();
});
document.addEventListener("htmx:after:swap", filterDeliveryBills);

// Calendar layer of the day pages: choosing a day closes it, htmx swaps the
// page behind it or the browser loads the day.
document.addEventListener("click", function(event) {
    var modal = event.target.closest("#day-calendar-modal");
    if (modal && event.target.closest(".day-calendar-cell.has-day")) {
        bootstrap.Modal.getOrCreateInstance(modal).hide();
    }
});

// Month calendar: the products of a day in a popover, which Bootstrap places
// where there is room. Made on the first hover or focus, htmx swaps the
// months. Touch screens have no hover, a tap opens the day.
["mouseover", "focusin"].forEach(function(type) {
    document.addEventListener(type, function(event) {
        // After a swap the focus can land on the document itself.
        if (!(event.target instanceof Element)) return;
        var cell = event.target.closest(".day-calendar .day-calendar-cell.has-day");
        if (!cell || bootstrap.Popover.getInstance(cell)) return;
        if (window.matchMedia("(hover: none)").matches) return;
        var tip = cell.querySelector(".day-calendar-tip");
        if (!tip) return;
        bootstrap.Popover.getOrCreateInstance(cell, {
            content: tip.innerHTML,
            html: true,
            trigger: "hover focus",
            placement: "bottom",
            fallbackPlacements: ["top", "right", "left"],
            container: "body",
            customClass: "day-calendar-popover",
        }).show();
    });
});
document.addEventListener("htmx:before:swap", function() {
    document.querySelectorAll(".day-calendar-cell.has-day").forEach(function(cell) {
        var popover = bootstrap.Popover.getInstance(cell);
        if (popover) popover.dispose();
    });
});

// Formsets with rows that can be added and removed: [data-formset] holds the
// rows, a <template data-formset-template> of the empty form and the buttons.
document.addEventListener('click', function (event) {
    var addButton = event.target.closest('[data-formset-add]');
    var removeButton = event.target.closest('[data-formset-remove]');
    if (addButton) {
        var formset = addButton.closest('[data-formset]');
        var total = formset.querySelector('[name="' + formset.dataset.formsetPrefix + '-TOTAL_FORMS"]');
        var template = formset.querySelector('[data-formset-template]');
        var holder = document.createElement('div');
        holder.innerHTML = template.innerHTML.replace(/__prefix__/g, total.value);
        total.value = parseInt(total.value, 10) + 1;
        formset.querySelector('[data-formset-rows]').appendChild(holder.firstElementChild);
    } else if (removeButton) {
        // The row stays in the form and is marked for deletion, so the
        // numbering of the other rows is kept.
        var row = removeButton.closest('[data-formset-row]');
        var deleteInput = row.querySelector('input[name$="-DELETE"]');
        if (deleteInput) {
            deleteInput.checked = true;
        }
        row.hidden = true;
    }
});
