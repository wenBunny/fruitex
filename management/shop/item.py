#!/usr/bin/env python
import csv
import re
from decimal import Decimal
from shop.models import Store, Category, Item, ItemMeta
from home.models import Item as HomeItem
from home.models import Store as HomeStore

def import_from_oldDb(store_name, category_full_name):
  # Warning: Assume store_name exists in HomeStore table
  print 'input store_name: '+store_name+' cat: '+category_full_name

  print 'Starting to import from Home database'

  newstore = Store.objects.filter(name = store_name)
  homestore = HomeStore.objects.filter(name = store_name)
  if not newstore.exists():
    print 'New store'+homestore[0].name+'created'
    newStore = Store.objects.create(
      name = homestore[0].name,
      slug = (homestore[0].name.lower()).replace(" ", "_"),
      address = homestore[0].address,
    )
  else:
    newStore = newstore[0]

  # Retrieve allItems:= items to be imported into new model
  if category_full_name == '':
    # Set flag to check category for each item when added
    check_cat = True
    allItems = HomeItem.objects.filter(store = homestore[0])
  else:
    allItems = HomeItem.objects.filter(
      store = homestore[0],
      category = category_full_name,
    )
    # Create category if needed
    # Duplicate code: to avoid check if category exists for every item later.
    check_cat = False
    category = None
    names = re.split('->', category_full_name)
    allCategories = Category.objects.filter(store = newStore)
    for name in names:
      categories = allCategories.filter(name = name)
      if category is None:
        categories = categories.filter(parent__isnull = True)
      else:
        categories = categories.filter(parent = category)
      if not categories.exists():
        category = Category.objects.create(
          name = name,
          slug = name.lower().replace(" ","_"),
          store = newStore,
          parent = category,
        )
      else:
        category = categories[0]

  print 'Starting to sweep thru allItems'
  for item in allItems:
    if check_cat:
      # Create category if needed
      category = None
      names = re.split('->', item.category)
      allCategories = Category.objects.filter(store = newStore)
      for name in names:
        categories = allCategories.filter(name = name)
        if category is None:
          categories = categories.filter(parent__isnull = True)
        else:
          categories = categories.filter(parent = category)
        if not categories.exists():
          category = Category.objects.create(
            name = name,
            slug = name.lower().replace(" ","_"),
            store = newStore,
            parent = category,
          )
        else:
          category = categories[0]
    # Special treatment for tax_class
    if item.tax_class == 'standard-rate':
      new_tax_class = 0.13
    elif item.tax_class == 'zero-rate':
      new_tax_class = 0.0
    else:
      # When tax_class EMPTY, fill 0.0 for now. Further manual work needed.
      new_tax_class = 0.0
      print 'Item: '+item.name+' lack TAX_CLASS, fill 0.0 temporary.'
    # Special treatment for out_of_stock
    if item.out_of_stock == 0:
      new_out_of_stock = False
    elif item.out_of_stock == 1:
      new_out_of_stock = True
    else:
      # When out_of_stock EMPTY, fill False.
      new_out_of_stock = False
      print 'Item: '+item.name+' lack OUT_OF_STOCK, fill FALSE temporary.'
    newitem = Item.objects.create(
      name = item.name,
      category = category,
      price = item.price,
      sales_price = item.sales_price,
      out_of_stock = new_out_of_stock,
      sku = item.sku,
      tax_class = new_tax_class,
      sold_number = item.sold_number,
    )
    # Add metadata for Remark when needed
    if not item.remark == '{}':
      new_remark = item.remark
      new_remark_title = 'remark'
      item_meta = ItemMeta.objects.create(
        item = newitem,
        key = new_remark_title,
        value = new_remark,
      )

def import_from_csv(filename, store_name):
  print 'Starting to import from CSV file %s' % filename
  with open(filename, 'rU') as csvfile:
    csvreader = csv.reader(csvfile)
    rownum = 0

    # Remember Col index
    name_index = -1
    category_index = -1
    description_index = -1
    sku_index = -1
    price_index = -1
    tax_class_index = -1

    # ItemMeta list
    metaList = dict()

    # Store
    StoreQS = Store.objects.filter(name=store_name)
    store = None
    if not StoreQS.exists():
      store = Store.objects.create(
        name = unicode(store_name),
        slug = (store_name.lower()).replace(" ", "_"),
        address = 'TBD'
      )
    else:
      store = StoreQS[0]

    for row in csvreader:
      if rownum == 0:
        # Store header row and recognize column name accordingly
        head = row
        rownum = 1
        for index, colname in enumerate(head):
          if colname == "Name":
              name_index = index
          elif colname == "Category":
              category_index = index
          elif colname == "Description":
              description_index = index
          elif colname == "SKU":
              sku_index = index
          elif colname == "Price":
              price_index = index
          elif colname == "Tax Class":
              tax_class_index = index
          else:
              # metaList (key=index, value = column_title)
              metaList[index] = colname
      else:
        try:
          item = Item()
          itemMeta = []
          for value, attribute in enumerate(row):
            # Add Item attributes according to column index
            if value == name_index:
              item.name = unicode(row[name_index])
            elif value == category_index:
              category = None
              names = re.split('->', row[category_index])
              allCategories = Category.objects.filter(store=store)

              # Split up Category content, iterate from top layer
              for name in names:
                categories = allCategories.filter(name=name)
                if category is None:
                  # If is top layer, try to find a category without parent
                  categories = categories.filter(parent__isnull=True)
                else:
                  categories = categories.filter(parent=category)

                if not categories.exists():
                  # If no such Category exists, create one
                  slug = name.lower().replace(" ", "_")
                  category = Category.objects.create(
                    name = name,
                    slug = slug,
                    store = store,
                    parent = category,
                  )
                else:
                  category = categories[0]

              # Assign Item's category since we know it exists now
              item.category = category
            elif value == description_index:
              item.description = unicode(row[description_index].decode('utf-8'))
            elif value == sku_index:
              item.sku = unicode(row[sku_index])
            elif value == price_index:
              item.price = Decimal(row[price_index])
            elif value == tax_class_index:
              item.tax_class = Decimal(row[tax_class_index])
            else:
              # Any other column index belong to metaData
              meta = ItemMeta()
              # Retrieve column name from metaList
              meta.key = unicode(metaList[value])
              meta.value = unicode(attribute)
              # We can't save itemMeta until the Item is saved
              itemMeta.append(meta)
          item.save()
        except Exception as e:
          print row[name_index]
          print e
        for meta in itemMeta:
          # Now Item is successfully saved, we can save all lingering meta
          meta.item = item
          meta.save()
