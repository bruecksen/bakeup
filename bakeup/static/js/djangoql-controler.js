class DjangoQLController extends window.StimulusModule.Controller {
    static values = { introspections: Object };

    connect() {
        // create
        console.log('connect', this.introspectionsValue);
        new DjangoQL({
            // either JS object with a result of DjangoQLSchema(MyModel).as_dict(),
            // or an URL from which this information could be loaded asynchronously
            introspections: this.introspectionsValue,

            // css selector for query input or HTMLElement object.
            // It should be a textarea
            selector: `#${this.element.id}`,

            // optional, you can provide URL for Syntax Help link here.
            // If not specified, Syntax Help link will be hidden.
            syntaxHelp: null,

            // optional, enable textarea auto-resize feature. If enabled,
            // textarea will automatically grow its height when entered text
            // doesn't fit, and shrink back when text is removed. The purpose
            // of this is to see full search query without scrolling, could be
            // helpful for really long queries.
            autoResize: true
        });

        // set options after initial creation
        setTimeout(() => {
            console.log('setTimeout')
        });
    }
}

window.wagtail.app.register('djangoql', DjangoQLController);
