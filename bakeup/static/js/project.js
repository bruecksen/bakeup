$(document).ready(function() {
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
    newForm.innerHTML = newForm.innerHTML.replace(/__prefix__/g, `${totalFormValue}`);
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


function setTotalBasketQuantity(modal, basket) {
    var totalBasketQuantity = 0;
    var totalBasketPrice = 0;
    modal.find('table tbody tr.product').each(function(){
        console.log($(this).data('basket-quantity'));
        if ($(this).data('basket-quantity')) {
            var quantity = parseInt(($(this).data('basket-quantity')));
            totalBasketQuantity += quantity;
        }
        if ($(this).data('product-price')) {
            var quantity = parseInt(($(this).data('basket-quantity')));
            if ($(this).data('ordered-quantity')){
                quantity = quantity + parseInt($(this).data('ordered-quantity'));
            }
            totalBasketPrice += quantity * parseFloat($(this).data('product-price')).toFixed(2);
        }
    });
    console.log('ttbasket:', totalBasketQuantity);
    console.log('ttbasket price:', totalBasketPrice);
    if (totalBasketPrice > 0) {
        modal.find('.price-total').html(totalBasketPrice.toLocaleString())
    } else {

    }

    if (totalBasketQuantity == 1) {
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
        $('header .shopping-basket .order-quantity').show().html(totalBasketQuantity);
        basket.find('.summary').hide();
        if (basket.hasClass('has-order')) {
            basket.find('.current-order').show();
        } else {
            basket.find('.empty').removeClass('d-none').show();
        }
        modal.find('form .form-check').removeClass('d-none').hide();
        modal.find('form button[type="submit"]').removeClass('d-none').hide();
        modal.find('form button[data-bs-dismiss="modal"]').show();
        modal.find('.modal-title span').removeClass('d-none').hide();
        modal.find('form input[type="reset"]').removeClass('d-none').hide();
    } else {
        basket.find('.summary').removeClass('d-none').show();
        basket.find('.empty').hide();
        if (totalBasketQuantity > 0) {
            $('header .shopping-basket .order-quantity').removeClass('d-none');
            $('header .shopping-basket .order-quantity').show().html(totalBasketQuantity);
        } else {
            $('header .shopping-basket .order-quantity').hide();
        }
        // modal.find("form").dirty("setAsDirty");
        modal.find("form .form-check").removeClass('d-none').show();
        modal.find('form button[type="submit"]').removeClass('d-none').show();
        modal.find('form button[data-bs-dismiss="modal"]').hide();
        modal.find('.modal-title span').removeClass('d-none').show();
        modal.find('form input[type="reset"]').removeClass('d-none').show();
        modal.find('.text-cancel').hide();
        modal.find('.text-change').show();
        
    }
}

function updateProduct(product, qty) {
    console.log('qty', qty);
    qty = parseInt(qty);
    var basket = $('#basket');
    var modal = $('.modal-checkout');
    basket.find('.summary').removeClass('d-none');
    basket.find('.current-order').hide();
    var row = $("tr[data-product='" + product + "']");
    var orderedQuantity = row.data('ordered-quantity');
    // set current product basket qty
    row.data('basket-quantity', qty);
    qty = orderedQuantity + qty;
    row.find('select.order-quantity').val(qty);
    if (qty > 0) {
        row.removeClass('d-none');
        row.show();
    } else if (qty == 0) {
        row.hide();
    }
    var totalQuantity = 0;
    var productPrice = row.data('product-price');
    if (productPrice) {
        productPrice = parseFloat(productPrice).toFixed(2);
        productPrice = qty * productPrice;
        row.find('.sale-price').html(productPrice.toLocaleString());
    }
    $('select.order-quantity').each(function(){
        totalQuantity += parseInt($(this).val());
    });
    setTotalBasketQuantity(modal, basket)
    basket.removeClass('d-none');
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
    var product = _this.data('product');
    updateProduct(product, val);
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
            var product = btn.getAttribute('data-product');
            updateProduct(product, value);
        })
    }
})
minus_btns.forEach(btn=>{
    if (!btn.nextElementSibling.disabled) {
        btn.addEventListener('click', ()=>{
            var value = (btn.nextElementSibling.value == 0) ? 0 : btn.nextElementSibling.value - 1;
            btn.nextElementSibling.value = value;
            var product = btn.getAttribute('data-product');
            updateProduct(product, value);
            })
        }
    })

$('.modal-checkout .btn-delete').click(function(){
    var tr = $(this).parents('tr');
    tr.fadeOut(function() {
        if ($(this).parents('tbody').children(':visible').length === 0) {
            $(this).parents('.modal-checkout').find('.text-cancel').removeClass('d-none').show();
            $(this).parents('.modal-checkout').find('.text-change').hide();
        }
    });
    tr.find('.order-quantity').val(0).change();

})
$('.modal-checkout form input[type="reset"]').click(function(){
    console.log('reset');
    var form = $(this).parents('form');
    form.find('tbody tr').show();
    form.find('.form-check').removeClass('d-none').hide();
    form.find('button[type="submit"]').removeClass('d-none').hide();
    form.find('input[type="reset"]').removeClass('d-none').hide();
    form.find('button[data-bs-dismiss="modal"]').show();
    form.dirty("setAsClean");

    var basket = $('#basket');
    $('header .shopping-basket .order-quantity').hide();
    // basket.find('.summary').hide();
    // basket.find('.empty').show();
    // basket.find('.current-order').show();
})

$(function(){
    $('.link-new-tab a').attr('target', '_blank');
    $('.link-new-tab a').attr('rel', 'nofollow noopener');
    if ($('.modal-checkout').length == 1) {
        $('.modal-checkout').on('hide.bs.modal', event => {
            console.log('hide', $('.modal-checkout form input[type="reset"]'));
            $('.modal-checkout form input[type="reset"]').click();
          })
        console.log('checkout exists');
        $('header .shopping-basket').addClass('d-lg-block');
    } else {
        console.log('checkout not');
        $('header .shopping-basket').removeClass('d-lg-block');
    }
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
    $('.modal-checkout form input, .modal-checkout form select').change(function() { 
        console.log('detect form change');
        var form = $(this).parents('form');
        var nowdata = form.serialize();
        // console.log(form, form.dirty('isClean'), form.dirty('isDirty'), form.dirty('showDirtyFields'));

        if (form.dirty('isClean')) {
            console.log('unchanged');
            form.find('.form-check.terms-conditions').removeClass('d-none').hide();
            form.find('button[type="submit"]').removeClass('d-none').hide();
            form.find('input[type="reset"]').removeClass('d-none').hide();
            form.find('button[data-bs-dismiss="modal"]').show();
            $(this).parents('.modal-checkout').find('.modal-title span').removeClass('d-none').hide();
        } else {
            console.log('changed');
            form.find('.form-check.terms-conditions').removeClass('d-none').show();
            form.find('input[type="reset"]').removeClass('d-none').show();
            form.find('button[type="submit"]').removeClass('d-none').show();
            form.find('button[data-bs-dismiss="modal"]').hide();
            $(this).parents('.modal-checkout').find('.modal-title span').removeClass('d-none').show();
            var product = $(this).parents('tr').data('product');
            var qty = this.value;
            if (product) {
                var orderedQty = $(this).parents('tr').data('ordered-quantity');
                if (orderedQty) {
                    console.log('detect qty select change to set total basket qty');
                    qty = Math.max(qty - orderedQty, 0);
                }
                console.log('product, changed: ', product);
                updateProduct(product, qty);
            }
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