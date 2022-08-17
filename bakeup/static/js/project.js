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