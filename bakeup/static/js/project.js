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
    var toastElList = [].slice.call(document.querySelectorAll('.toast'))
    var toastList = toastElList.map(function(toastEl) {
    // Creates an array of toasts (it only initializes them)
        return new bootstrap.Toast(toastEl) // No need for options; use the default options
    });
    console.log(toastList);
    toastList.forEach(toast => toast.show()); // This show them
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


var form = document.querySelectorAll(".form-container");
var container = document.querySelector(".form-add-inline");
var addAnotherContainer = document.querySelector(".add-another-container");
var addButton = document.querySelector(".add-another-form");
var totalForms = document.querySelector("#id_form-TOTAL_FORMS");
var saveButton = document.querySelector(".save-another-form");
if (addButton) {
    addButton.addEventListener('click', addForm);
}

function addRemoveButtonEvent(removeButtons) {
    for (let i = 0; i < removeButtons.length; i++) {
        removeButtons[i].addEventListener("click", removeForm);
    }
}


function addForm(e){
    e.preventDefault();
    saveButton.classList.remove('d-none');
    var totalFormValue = parseInt(totalForms.value);
    var newForm = form[0].cloneNode(true);
    var formRegex = RegExp(`form-(\\d){1}-`,'g');

    newForm.classList.remove('d-none');
    console.log(newForm);
    newForm.innerHTML = newForm.innerHTML.replace(/__prefix__/g, `${totalFormValue}`);
    newForm.querySelector(`#id_form-${totalFormValue}-weight`).required = true;
    console.log(form[0])
    container.insertBefore(newForm, form[0]);

    totalForms.setAttribute('value', `${totalFormValue+1}`);
    var removeButtons = document.querySelectorAll(".remove-another-form");
    addRemoveButtonEvent(removeButtons);

}

var removeButtons = document.querySelectorAll(".remove-another-form");

addRemoveButtonEvent(removeButtons);

function removeForm(e) {
    console.log('click');
    e.preventDefault();
    e.target.closest('.list-group-item').remove();
    var totalFormValue = parseInt(document.querySelector("#id_form-TOTAL_FORMS").value);
    totalForms.setAttribute('value', `${totalFormValue-1}`);
    if (totalFormValue - 1 == 0) {
        saveButton.classList.add('d-none');
    }
}

// toggle Sidebar
var sidebarToggler = document.querySelector(".sidebar-toggler");
if (sidebarToggler) {
    sidebarToggler.addEventListener('click', toggleSidebar);
}
var sidebarTogglerHide = document.querySelector('.sidebar-toggler-hide');
if (sidebarTogglerHide) {
    sidebarTogglerHide.addEventListener('click', toggleSidebar);
}
function toggleSidebar() {
    const el = document.querySelector( '.sidebar' );
    if( window.getComputedStyle( el ).display === "none" ) {
        el.style.display = "flex";
        sidebarTogglerHide.style.display = 'block';
    } else {
        el.style.display = ""; // unset flex, so it returns to `none` as defined in the CSS.
        sidebarTogglerHide.style.display = '';
    }
}

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
