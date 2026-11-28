// Tab control: a row of tabs and the panel of the selected one. Other elements may follow the tab
// list in that row, e.g. a toolbar:
//   <tab-control>
//     <div role="tablist" aria-label="Test cases"><button>1</button><button>2</button></div>
//     <div id="active_test" role="tabpanel">...</div>
//   </tab-control>
// The tabs share the panel: the page fills it when the tab control sends a change event, whose
// detail is the index of the selected tab. Arrows, Home, and End move between the tabs. The page
// may add or remove buttons of the tab list, and then calls update()
class TabControl extends HTMLElement {
  connectedCallback() {
    // The panel that shows the selected tab, HTMLElement
    this.panel = this.querySelector(':scope > [role="tabpanel"]');
    this.update();
    // The list takes the clicks and keys of its tabs, also of the ones added later
    const list = this.querySelector(':scope > [role="tablist"]');
    list?.addEventListener('click', (event) => {
      const index = this.tabs.indexOf(event.target.closest('button'));
      if (index >= 0) {
        this.select(index);
      }
    });
    list?.addEventListener('keydown', (event) => this.move(event));
  }

  // Finds the buttons of the tab list again, and makes them tabs of the panel
  update() {
    // The buttons of the tab list, HTMLButtonElement[]
    this.tabs = [...this.querySelectorAll(':scope > [role="tablist"] > button')];
    this.tabs.forEach((tab, index) => {
      tab.role = 'tab';
      tab.id = `${this.panel.id}_tab_${index + 1}`;
      tab.setAttribute('aria-controls', this.panel.id);
    });
  }

  // Index of the selected tab, or -1 if none is selected
  get selectedIndex() {
    return this.tabs.findIndex((tab) => tab.ariaSelected === 'true');
  }

  // Selects the tab at the index without telling the page. Only the selected tab is in the order
  // of the Tab key, and the arrows move between the others
  set selectedIndex(index) {
    this.tabs.forEach((tab, position) => {
      tab.ariaSelected = String(position === index);
      tab.tabIndex = position === index ? 0 : -1;
    });
    this.panel.setAttribute('aria-labelledby', this.tabs[index].id);
    // A long tab list scrolls itself to show the selected tab in its middle, without scrolling
    // the page as scrollIntoView() would
    const list = this.tabs[index].parentElement;
    const { top, height } = this.tabs[index].getBoundingClientRect();
    list.scrollTop += top - list.getBoundingClientRect().top - (list.clientHeight - height) / 2;
  }

  // Selects the tab at the index and tells the page with a change event
  select(index) {
    this.selectedIndex = index;
    this.dispatchEvent(new CustomEvent('change', { detail: index }));
  }

  // The arrows select the tab before or after the selected one, going around at the ends, and
  // Home and End select the first or the last tab
  move(event) {
    const { length } = this.tabs;
    const index = {
      ArrowLeft: this.selectedIndex - 1,
      ArrowRight: this.selectedIndex + 1,
      Home: 0,
      End: length - 1,
    }[event.key];
    if (index !== undefined) {
      event.preventDefault();
      this.select((index + length) % length);
      this.tabs[this.selectedIndex].focus();
    }
  }
}

customElements.define('tab-control', TabControl);
