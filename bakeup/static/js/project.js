$(document).ready(function() {
    if (location.hash) {
        $("button[data-bs-target='" + location.hash + "']").tab("show");
    }
    $(document.body).on("click", "button[data-bs-toggle='tab']", function(event) {
        location.hash = this.getAttribute("data-bs-target");
    });
    $('#customer-order-form').dirty({
        preventLeaving: true,
        leavingMessage: 'Du hast deinen Brotkorb noch nicht abgeschickt. Willst du wirklich die Seite verlassen?', 
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


let form = document.querySelectorAll(".form-container");
let container = document.querySelector(".form-add-inline");
let addAnotherContainer = document.querySelector(".add-another-container");
let addButton = document.querySelector(".add-another-form");
let totalForms = document.querySelector("#id_form-TOTAL_FORMS");
let saveButton = document.querySelector(".save-another-form");
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
    let totalFormValue = parseInt(totalForms.value);
    let newForm = form[0].cloneNode(true);
    let formRegex = RegExp(`form-(\\d){1}-`,'g');

    newForm.classList.remove('d-none');
    newForm.innerHTML = newForm.innerHTML.replace(/__prefix__/g, `${totalFormValue}`);
    console.log(form[0])
    container.insertBefore(newForm, form[0]);
    
    totalForms.setAttribute('value', `${totalFormValue+1}`);
    let removeButtons = document.querySelectorAll(".remove-another-form");
    addRemoveButtonEvent(removeButtons);
    
}

let removeButtons = document.querySelectorAll(".remove-another-form");

addRemoveButtonEvent(removeButtons);

function removeForm(e) {
    console.log('click');
    e.preventDefault();
    e.target.closest('.list-group-item').remove();
    let totalFormValue = parseInt(document.querySelector("#id_form-TOTAL_FORMS").value);
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
    var modalEl = document.getElementById('checkout');
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
})

$('#checkout .btn-delete').click(function(){
    console.log('clic');
    var tr = $(this).parents('tr');
    tr.fadeOut();
    tr.find('.order-quantity').val(0);
})

function updateProduct(product, qty) {
    var basket = $('#basket');
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
    $('select.order-quantity').each(function(){
        totalQuantity += parseInt($(this).val());
    });
    var totalBasketQuantity = 0;
    $('#checkout table tbody tr').each(function(){
        totalBasketQuantity += $(this).data('basket-quantity');
    });
    console.log('ttbasket:', totalBasketQuantity);

    if (totalBasketQuantity == 1) {
        basket.find('.single').show();
        basket.find('.plural').hide()
        
    } else if (totalBasketQuantity > 1) {
        basket.find('.plural').show();
        basket.find('.single').hide();
        basket.find('.plural .qty').html(totalBasketQuantity);
    }
    if (totalBasketQuantity > 0) {
        basket.find('.summary').show();
        basket.find('.empty').hide();
        $('header .shopping-basket .order-quantity').removeClass('d-none');
        $('header .shopping-basket .order-quantity').show().html(totalBasketQuantity);
        $("#customer-order-form").dirty("setAsDirty");
    } else {
        $('header .shopping-basket .order-quantity').hide();
        basket.find('.summary').hide();
        basket.find('.empty').show();
        basket.find('.current-order').show();
        $("#customer-order-form").dirty("setAsClean");

    }
    basket.removeClass('d-none');

}

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



var navbar = document.getElementById('navbar');
if(!navbar.classList.contains('nav-bg-dark')) {
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

// $(function() {
//     var offset = 77;
//     var boxInitialTop = $('.sticky').offset().top;
//     var width = $('.sticky').width();
//     console.log('width: ', width);
//     $(window).scroll(function () {
//       if ($(window).scrollTop() > boxInitialTop - offset) {
//         $('.sticky').css({position: 'fixed', top: offset + 'px', width: width + 'px'});
//       } else {
//         $('.sticky').css({position: 'static', width: 'auto'});
//       }
//     });
// });