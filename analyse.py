<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>Form</class>
 <widget class="QWidget" name="Form">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>978</width>
    <height>717</height>
   </rect>
  </property>
  <property name="windowTitle">
   <string>Form</string>
  </property>
  <widget class="QLabel" name="H_label_h">
   <property name="geometry">
    <rect>
     <x>200</x>
     <y>660</y>
     <width>61</width>
     <height>19</height>
    </rect>
   </property>
   <property name="font">
    <font>
     <weight>75</weight>
     <bold>true</bold>
    </font>
   </property>
   <property name="text">
    <string>H (A/m)</string>
   </property>
  </widget>
  <widget class="QLabel" name="B_label_h">
   <property name="geometry">
    <rect>
     <x>0</x>
     <y>480</y>
     <width>41</width>
     <height>20</height>
    </rect>
   </property>
   <property name="font">
    <font>
     <weight>75</weight>
     <bold>true</bold>
    </font>
   </property>
   <property name="text">
    <string>B (T)</string>
   </property>
  </widget>
  <widget class="QLabel" name="B_label">
   <property name="geometry">
    <rect>
     <x>390</x>
     <y>80</y>
     <width>41</width>
     <height>20</height>
    </rect>
   </property>
   <property name="font">
    <font>
     <weight>75</weight>
     <bold>true</bold>
    </font>
   </property>
   <property name="text">
    <string>B (T)</string>
   </property>
  </widget>
  <widget class="QLabel" name="H_label">
   <property name="geometry">
    <rect>
     <x>20</x>
     <y>80</y>
     <width>61</width>
     <height>19</height>
    </rect>
   </property>
   <property name="font">
    <font>
     <weight>75</weight>
     <bold>true</bold>
    </font>
   </property>
   <property name="text">
    <string>H (A/m)</string>
   </property>
  </widget>
  <widget class="QSpinBox" name="N_harmonique_spinBox">
   <property name="geometry">
    <rect>
     <x>200</x>
     <y>220</y>
     <width>61</width>
     <height>28</height>
    </rect>
   </property>
  </widget>
  <widget class="QLabel" name="label_5">
   <property name="geometry">
    <rect>
     <x>30</x>
     <y>220</y>
     <width>161</width>
     <height>20</height>
    </rect>
   </property>
   <property name="text">
    <string>Nombre harmoniques</string>
   </property>
  </widget>
  <widget class="MplWidget" name="widget_analyse" native="true">
   <property name="geometry">
    <rect>
     <x>40</x>
     <y>260</y>
     <width>521</width>
     <height>401</height>
    </rect>
   </property>
  </widget>
  <widget class="MplWidget" name="widget_H" native="true">
   <property name="geometry">
    <rect>
     <x>80</x>
     <y>20</y>
     <width>281</width>
     <height>161</height>
    </rect>
   </property>
  </widget>
  <widget class="MplWidget" name="widget_B" native="true">
   <property name="geometry">
    <rect>
     <x>440</x>
     <y>20</y>
     <width>281</width>
     <height>161</height>
    </rect>
   </property>
  </widget>
  <widget class="QPushButton" name="import_button">
   <property name="geometry">
    <rect>
     <x>770</x>
     <y>40</y>
     <width>181</width>
     <height>25</height>
    </rect>
   </property>
   <property name="text">
    <string>Sélectionner les courbes</string>
   </property>
  </widget>
  <widget class="QPushButton" name="clear_button">
   <property name="geometry">
    <rect>
     <x>770</x>
     <y>70</y>
     <width>181</width>
     <height>25</height>
    </rect>
   </property>
   <property name="text">
    <string>Effacer les courbes</string>
   </property>
  </widget>
  <widget class="QPushButton" name="colors_button">
   <property name="geometry">
    <rect>
     <x>770</x>
     <y>100</y>
     <width>181</width>
     <height>25</height>
    </rect>
   </property>
   <property name="text">
    <string>Changer les couleurs</string>
   </property>
  </widget>
  <widget class="QPushButton" name="export_table_button">
   <property name="geometry">
    <rect>
     <x>770</x>
     <y>130</y>
     <width>181</width>
     <height>25</height>
    </rect>
   </property>
   <property name="text">
    <string>Exporter la table</string>
   </property>
  </widget>
  <widget class="QLabel" name="Pv_label">
   <property name="geometry">
    <rect>
     <x>580</x>
     <y>500</y>
     <width>171</width>
     <height>20</height>
    </rect>
   </property>
   <property name="text">
    <string>Pertes volumiques (W/kg)</string>
   </property>
  </widget>
  <widget class="QLabel" name="Pv_value">
   <property name="geometry">
    <rect>
     <x>780</x>
     <y>500</y>
     <width>66</width>
     <height>19</height>
    </rect>
   </property>
   <property name="text">
    <string>TextLabel</string>
   </property>
  </widget>
  <widget class="QLabel" name="Aire_label">
   <property name="geometry">
    <rect>
     <x>580</x>
     <y>470</y>
     <width>81</width>
     <height>19</height>
    </rect>
   </property>
   <property name="text">
    <string>Aire (J/m3)</string>
   </property>
  </widget>
  <widget class="QLabel" name="Aire_value">
   <property name="geometry">
    <rect>
     <x>780</x>
     <y>470</y>
     <width>66</width>
     <height>19</height>
    </rect>
   </property>
   <property name="text">
    <string>TextLabel</string>
   </property>
  </widget>
 </widget>
 <customwidgets>
  <customwidget>
   <class>MplWidget</class>
   <extends>QWidget</extends>
   <header>mplwidget.h</header>
   <container>1</container>
  </customwidget>
 </customwidgets>
 <resources/>
 <connections/>
</ui>
