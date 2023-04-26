$(document).ready(function() {
    if (location.hash) {
        $("button[data-bs-target='" + location.hash + "']").tab("show");
    }
    $(document.body).on("click", "button[data-bs-toggle='tab']", function(event) {
        location.hash = this.getAttribute("data-bs-target");
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
let plus_btns = document.querySelectorAll('.input-group .btn-plus');
let minus_btns = document.querySelectorAll('.input-group .btn-minus');
let qty_inputs = document.querySelectorAll('.input-group input[type=number]');
console.log(plus_btns, minus_btns, qty_inputs);
   plus_btns.forEach(btn=>{
    console.log(btn.disabled)
    if (!btn.previousElementSibling.disabled){
        btn.addEventListener('click', ()=>{
         console.log(btn.previousElementSibling.value == btn.previousElementSibling.max);
            btn.previousElementSibling.value = (btn.previousElementSibling.value == btn.previousElementSibling.max) ? btn.previousElementSibling.max : parseInt(btn.previousElementSibling.value) + 1;
        })
    }
    })
    minus_btns.forEach(btn=>{
        if (!btn.nextElementSibling.disabled) {
            btn.addEventListener('click', ()=>{
                 btn.nextElementSibling.value = (btn.nextElementSibling.value == 0) ? 0 : btn.nextElementSibling.value - 1;
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
