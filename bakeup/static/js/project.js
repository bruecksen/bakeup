/* Project specific Javascript goes here. */


$('.add-another').click(function(){
    console.log('click');
});

let form = document.querySelectorAll(".form-container");
let container = document.querySelector(".form-add-inline");
let addAnotherContainer = document.querySelector(".add-another-container");
let addButton = document.querySelector("#add-another-form");
let totalForms = document.querySelector("#id_form-TOTAL_FORMS");
addButton.addEventListener('click', addForm);

function addForm(e){
    e.preventDefault();
    
    let totalFormValue = parseInt(totalForms.value);
    let newForm = form[0].cloneNode(true);
    let formRegex = RegExp(`form-(\\d){1}-`,'g');

    newForm.classList.remove('d-none');
    newForm.innerHTML = newForm.innerHTML.replace(/__prefix__/g, `${totalFormValue}`);
    container.insertBefore(newForm, form[0]);
    
    totalForms.setAttribute('value', `${totalFormValue+1}`);
}