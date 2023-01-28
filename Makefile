PACKAGE = io_export_objex2

PY = $(shell find -maxdepth 1 -type f -name '*.py')
DS = $(foreach f, $(PY:./%=%), .tmp/$(PACKAGE)/$f)

$(shell mkdir -p .tmp/$(PACKAGE))

release: $(DS)
	rm -f $(PACKAGE).zip
	cd .tmp/ && zip -r ../$(PACKAGE).zip $(PACKAGE)

clean:
	rm -f $(PACKAGE).zip
	rm -rf .tmp

.tmp/$(PACKAGE)/%.py: %.py
	cp $< $@

say:
	@echo $(DS)
